"""Container-local provisioning/acceptance checks. No secrets in output."""
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import ssl
import sys
import tarfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

PRIVATE = Path("/private")


def secret(name):
    return (PRIVATE / "secrets" / name).read_text().strip()


def call(url, data=None, headers=None, method=None, user=None):
    headers = dict(headers or {})
    if user:
        password = secret("grafana_admin_password" if user == "admin" else user + "_password")
        headers["Authorization"] = "Basic " + base64.b64encode((user + ":" + password).encode()).decode()
    if isinstance(data, dict):
        data = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
    context = ssl.create_default_context(cafile=str(PRIVATE / "tls/ca.crt"))
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=context))
    try:
        with opener.open(req, timeout=10) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()


def wait():
    for attempt in range(60):
        try:
            if call("https://grafana:3000/api/health")[0] == 200 and call("http://nodered:1880/auth/login")[0] == 200:
                return
        except (URLError, TimeoutError):
            pass
        time.sleep(1)
    raise RuntimeError("Grafana/Node-RED readiness timed out; inspect project logs")


def users():
    wait()
    status, data = call("https://grafana:3000/api/org/users", user="admin")
    assert status == 200, "Admin login failed"
    existing = {u["login"] for u in json.loads(data)}
    for login, role in (("researcher", "Editor"), ("viewer", "Viewer")):
        if login in existing:
            print("Existing account preserved:", login)
            continue
        status, data = call("https://grafana:3000/api/admin/users", {
            "name": login.title(), "login": login, "email": login + "@edgeclimate.invalid",
            "password": secret(login + "_password"), "OrgId": 1,
        }, user="admin")
        assert status == 200, "Account creation failed"
        uid = json.loads(data)["id"]
        status, _ = call("https://grafana:3000/api/org/users/" + str(uid), {"role": role}, method="PATCH", user="admin")
        assert status == 200, "Role assignment failed"
        print("Created", login, "role=" + role)


def verify():
    wait()
    assert call("https://grafana:3000/api/search")[0] == 401, "Anonymous Grafana access permitted"
    assert call("http://nodered:1880/flows")[0] == 401, "Anonymous Node-RED editor access permitted"
    assert call("http://nodered:1880/ingest", {"reading": {}})[0] == 401, "Unauthenticated ingest permitted"
    from urllib.parse import urlencode
    login = urlencode({"client_id": "node-red-admin", "grant_type": "password", "scope": "*",
                       "username": "admin", "password": secret("nodered_admin_password")}).encode()
    status, body = call("http://nodered:1880/auth/token", login,
                        {"Content-Type": "application/x-www-form-urlencoded"})
    assert status == 200 and json.loads(body).get("access_token"), "Node-RED admin authentication failed"
    for user in ("viewer", "researcher"):
        status, body = call("https://grafana:3000/api/dashboards/uid/edgeclimate", user=user)
        assert status == 200 and "EdgeClimate" in json.loads(body)["dashboard"]["title"], "Dashboard read failed"
    dashboard = {"dashboard": {"id": None, "uid": "edge-role-test", "title": "Edge role acceptance test", "schemaVersion": 41, "panels": []}, "overwrite": True}
    assert call("https://grafana:3000/api/dashboards/db", dashboard, user="viewer")[0] == 403, "Viewer could edit"
    assert call("https://grafana:3000/api/dashboards/db", dashboard, user="researcher")[0] == 200, "Editor could not edit"
    assert call("https://grafana:3000/api/dashboards/uid/edge-role-test", method="DELETE", user="researcher")[0] == 200
    query = b'from(bucket:"environment") |> range(start:-1h) |> limit(n:5)'
    def influx_query(token):
        return call("http://influxdb:8086/api/v2/query?org=edgeclimate", query, {
            "Authorization": "Token " + token, "Content-Type": "application/vnd.flux", "Accept": "application/csv"})
    # InfluxDB hides unreadable buckets behind 404, rather than disclosing them.
    # The same query with the reader token must succeed below against real data.
    denied_status, denied_body = influx_query(secret("influx_write_token"))
    assert denied_status in (401, 403, 404), "Writer unexpectedly has read access"
    if denied_status == 404:
        assert json.loads(denied_body).get("code") == "not found", "Unexpected missing-bucket response"
    assert call("http://influxdb:8086/api/v2/write?org=edgeclimate&bucket=environment&precision=ms",
                b'forbidden value=1', {"Authorization": "Token " + secret("influx_read_token"),
                "Content-Type": "text/plain"})[0] in (401, 403), "Reader unexpectedly has write access"
    reading = {"reading": {"temperature": 22.5, "humidity": 50, "pressure": 1013.25},
               "source": "simulated", "sensor_id": "acceptance-test", "location": "test"}
    headers = {"Authorization": "Bearer " + secret("ingest_token")}
    assert call("http://nodered:1880/ingest", reading, headers)[0] == 204, "Valid ingestion failed"
    reading["reading"]["humidity"] = 150
    assert call("http://nodered:1880/ingest", reading, headers)[0] == 400, "Invalid reading accepted"
    # Wait for persistence visibility and verify actual data, not merely a running port.
    for attempt in range(15):
        status, body = influx_query(secret("influx_read_token"))
        if status == 200 and b"acceptance-test" in body:
            break
        time.sleep(1)
    else:
        raise AssertionError("Ingested test measurement not found in InfluxDB")
    flux_payload = {"queries": [{"refId": "A", "datasource": {"type": "influxdb", "uid": "edge-influx"},
                               "query": 'from(bucket:"environment") |> range(start:-1h) |> filter(fn:(r)=>r.sensor_id == "acceptance-test") |> limit(n:5)'}],
                    "from": str(int((time.time() - 3600) * 1000)), "to": str(int(time.time() * 1000))}
    status, body = call("https://grafana:3000/api/ds/query", flux_payload, user="viewer")
    assert status == 200, "Grafana datasource query failed"
    result = json.loads(body)["results"]["A"]
    assert not result.get("error") and result.get("frames"), "Grafana returned no data frames"
    print("PASS: TLS verification, anonymous denials, Viewer/Editor permissions, scoped service tokens,")
    print("      valid/invalid ingestion, Influx persistence and authenticated Grafana datasource query.")
    print("NOT VERIFIED HERE: real USB sensor, live weather, Pi hotspot, physical router-off demonstration.")


def backup():
    directory = PRIVATE / "backups"
    directory.mkdir(mode=0o700, exist_ok=True)
    config = dict(line.split("=", 1) for line in (PRIVATE / "config.env").read_text().splitlines()
                  if line.strip() and not line.lstrip().startswith("#"))
    owner = (int(config.get("EDGE_UID", "1000")), int(config.get("EDGE_GID", "1000")))
    os.chown(directory, *owner)
    archive = directory / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".tar.gz")
    with archive.open("xb") as stream:
        os.chmod(archive, 0o600)
        os.chown(archive, *owner)
        with tarfile.open(fileobj=stream, mode="w:gz") as tar:
            for name in ("influx", "grafana", "nodered"):
                tar.add("/volumes/" + name, arcname="volumes/" + name)
            for name in ("secrets", "tls", "config.env"):
                tar.add(PRIVATE / name, arcname="private/" + name)
    with tarfile.open(archive) as tar:
        names = tar.getnames()
        assert "private/config.env" in names and "volumes/influx" in names
    print("Cold backup created and archive structure checked:", archive.name)
    print("Contains credentials: keep private, encrypt off-device copies. Restore rehearsal is still required.")


def benchmark():
    from concurrent.futures import ThreadPoolExecutor
    wait()
    headers = {"Authorization": "Bearer " + secret("ingest_token")}
    def send(index):
        start = time.monotonic()
        reading = {"reading": {"temperature": 20 + index % 5, "humidity": 50, "pressure": 1010},
                   "source": "simulated", "sensor_id": "loadtest-" + str(index % 10), "location": "benchmark"}
        try:
            status, _ = call("http://nodered:1880/ingest", reading, headers)
        except (URLError, TimeoutError):
            status = 0
        return status, time.monotonic() - start
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(send, range(100)))
    elapsed = time.monotonic() - started
    latencies = sorted(t for _, t in results)
    success = sum(status == 204 for status, _ in results)
    print(json.dumps({"label": "synthetic ingest benchmark, 10 simulated sensor IDs, 4 clients",
                      "requests": 100, "acknowledged": success, "failed": 100 - success,
                      "elapsed_seconds": round(elapsed, 3), "requests_per_second": round(100 / elapsed, 2),
                      "p50_ms": round(latencies[49] * 1000, 2), "p95_ms": round(latencies[94] * 1000, 2)}, indent=2))
    print("This measures ingestion acknowledgements, not dashboard concurrency or horizontal scalability.")
    assert success == 100, "Benchmark had failed writes"


if __name__ == "__main__":
    try:
        {"users": users, "verify": verify, "backup": backup, "benchmark": benchmark}[sys.argv[1]]()
    except (AssertionError, RuntimeError) as error:
        raise SystemExit(str(error)) from None

"""First-run Influx bootstrap; scoped service tokens, never printed to logs."""
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

BASE = "http://influxdb:8086"
SECRETS = Path("/secrets")
OPENER = build_opener(ProxyHandler({}))  # Only the internal InfluxDB URL is used.


def request(path, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Token " + token
    req = Request(BASE + path, data=None if data is None else json.dumps(data).encode(), headers=headers)
    with OPENER.open(req, timeout=10) as response:
        return json.load(response)


def main():
    for attempt in range(60):
        try:
            setup = request("/api/v2/setup")
            break
        except (URLError, TimeoutError):
            if attempt == 59:
                raise RuntimeError("InfluxDB did not become ready") from None
            time.sleep(1)
    admin = (SECRETS / "influx_admin_token").read_text().strip()
    org_name = os.getenv("INFLUX_ORG", "edgeclimate")
    bucket_name = os.getenv("INFLUX_BUCKET", "environment")
    if setup["allowed"]:
        request("/api/v2/setup", {
            "username": "edge-admin", "password": (SECRETS / "influx_admin_password").read_text().strip(),
            "org": org_name, "bucket": bucket_name, "retentionPeriodSeconds": 90 * 86400,
            "token": admin,
        })
    orgs = request("/api/v2/orgs", token=admin)["orgs"]
    org = next(o for o in orgs if o["name"] == org_name)
    buckets = request("/api/v2/buckets?orgID=" + org["id"], token=admin)["buckets"]
    bucket = next(b for b in buckets if b["name"] == bucket_name)
    for action in ("read", "write"):
        path = SECRETS / f"influx_{action}_token"
        # Zero-length placeholders are created before Compose binds the files.
        if path.read_text().strip():
            continue
        auth = request("/api/v2/authorizations", {
            "orgID": org["id"], "description": f"edgeclimate-{action}",
            "permissions": [{"action": action, "resource": {
                "type": "buckets", "id": bucket["id"], "orgID": org["id"],
            }}],
        }, token=admin)
        path.write_text(auth["token"] + "\n")
        path.chmod(0o600)
    print("Influx ready: environment bucket, 90-day retention, separate read/write tokens")


if __name__ == "__main__":
    try:
        main()
    except HTTPError as error:
        raise SystemExit(f"Influx provisioning HTTP {error.code}; inspect configuration without exposing tokens") from None

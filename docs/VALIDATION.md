# Validation in the cloud development environment

Prepared and checked on 2026-11-07, Linux x86_64 using the managed rootless
Docker daemon. This is evidence for the software stack, not a Pi hardware test.

| Check | Result |
|---|---|
| Compose configuration | Passed |
| Node validation/weather tests | 9 passed |
| Linux serial parser with pseudo-terminal | 1 passed, including malformed/oversized input |
| Simulator → Node-RED → InfluxDB → Grafana query | Passed |
| Grafana HTTPS certificate verification | Passed using generated CA |
| Anonymous Grafana, editor and ingest requests denied | Passed |
| Node-RED administrator authentication | Passed |
| Grafana Viewer read/edit denied; Editor edit allowed | Passed |
| Write-only token query denied | Passed; Influx hides unreadable bucket with HTTP 404 |
| Read-only token write denied | Passed |
| Invalid measurements rejected | Passed |
| Node-RED login form in Chromium | Passed |
| Repeat init, cold backup archive and restart | Passed; roles/data preserved |
| Full archive restoration | Not run |
| Physical Arduino, sketch compilation and BME280 readings | Not run: IDE shows UNO selected; actual serial format/baud not confirmed |
| Live Open-Meteo request | Blocked by cloud outbound policy; domain addition saved for review |
| Pi AP capability, mobile access and physical router-off test | Not run |

A small **synthetic ingestion benchmark** used 100 requests, four concurrent
clients and 10 simulated sensor IDs. All 100 were acknowledged. Observed run:
0.624 seconds total, 160.16 requests/second, p50 23.20 ms, p95 41.00 ms.
These figures describe this short cloud run, not Pi capacity, simultaneous
dashboard users, maximum sustainable throughput or distinct stored-point count.
Re-run and expand the experiment on the Pi before making scalability claims.
Rootless daemon metrics without cgroup accounting may not provide meaningful
per-container CPU/memory isolation; validate metrics on the target platform.

Commands to reproduce the software checks:

```sh
node --test edge/tests/logic.test.js
python3 -m unittest discover -s edge/tests -p 'test_*.py'
./scripts/edge demo
./scripts/edge verify
./scripts/edge benchmark
./scripts/edge backup
./scripts/edge demo
./scripts/edge verify
```

Weather fixtures test UTC model-valid-time preservation, stale/future rejection
and explicit units. They do not replace testing the live API. Repeated weather
fetches retain model valid time, so they cannot falsely refresh outdoor age.
Live weather is disabled in the current cloud test instance; the example Pi
configuration enables weather for Wolverhampton.

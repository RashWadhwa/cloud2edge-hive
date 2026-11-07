# EdgeClimate

**Secure Offline Environmental Monitoring with Cloud Weather Context**

An Arduino UNO and BME280 send indoor temperature, humidity and pressure over
USB to a Raspberry Pi. Node-RED validates readings and calculates dew point;
InfluxDB stores them for 90 days; Grafana displays live values and history with
local authentication and Viewer, Editor and Admin permissions.

Open-Meteo supplies optional outdoor weather estimates for Wolverhampton.
Indoor sensing and storage continue when the router is off. Weather updates
stop, and the dashboard shows their age rather than presenting cached data as
fresh. The public non-commercial weather endpoint requires no API key.

## Start on the Pi

Use the `main` branch. See [deployment instructions](docs/DEPLOY.md) for updating
an existing checkout while preserving local commits and settings.

```sh
./scripts/edge init
# Edit .edge/config.env: actual Arduino device path and matching serial baud.
# With the Arduino emitting the documented JSON-lines format:
./scripts/edge up
./scripts/edge verify
```

For a software-only rehearsal:

```sh
./scripts/edge demo
./scripts/edge verify
```

Simulation is explicitly labelled and excluded from the physical sensor panels.
The stack is defined in `compose.edge.yml`; use `./scripts/edge` to manage it.

- [Project architecture, security, accounts and router-off experiment](docs/PROJECT.md)
- [Pi deployment and updates](docs/DEPLOY.md)
- [Validation results and limitations](docs/VALIDATION.md)

The project uses the Arduino/BME280 connection and does not require a Zigbee
coordinator. The old Hive/Zigbee service configuration has been retired from
current source. Existing Pi runtime data remains untouched; credentials and
settings belong in ignored `.edge/` files.

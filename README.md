# cloud2edge-hive

**Current project: EdgeClimate — Secure Offline Environmental Monitoring with
Cloud Weather Context.** Uses your existing Arduino/BME280 over USB, Node-RED,
InfluxDB, Grafana, local multi-user roles and optional Open-Meteo weather.
See [the project and setup guide](docs/PROJECT.md) for installation, credentials,
security scope and the router-off experiment. No external API key is needed
for the public non-commercial weather endpoint.

```sh
./scripts/edge init
# Edit .edge/config.env for your actual Arduino and approximate weather location.
# Software-only validation (clearly labelled simulated data):
./scripts/edge demo
./scripts/edge verify
# With your Arduino configured and emitting JSON lines:
# ./scripts/edge up
```

This is a separate Compose project (`compose.edge.yml`) and preserves the
existing Hive setup below. Keep the SLT3b paired with its Hive hub.

## Original Hive workflow

Collect room temperature on a Raspberry Pi. A Hive device reports over Zigbee to a USB coordinator. Zigbee2MQTT publishes the readings to Mosquitto, and Home Assistant displays the current reading and records its history.

## Start on the Pi

Use a 64-bit Raspberry Pi OS with Docker and the Compose plugin. Plug in one Zigbee coordinator and run these commands from the repository root.

```sh
ls -l /dev/serial/by-id/
cp -n .env.example .env
nano .env
```

Set `ZIGBEE_DEVICE` to the full `/dev/serial/by-id/...` path for your coordinator. Compose maps that path to `/dev/ttyUSB0` inside the container. The supplied configuration uses `ember` for the SONOFF Dongle Plus MG24 with Zigbee coordinator firmware. If you're using the original TI-based ZBDongle-P, set `serial.adapter` to `zstack` in the runtime configuration before starting. [Zigbee2MQTT adapter guide](https://www.zigbee2mqtt.io/guide/adapters/)

```sh
mkdir -p zigbee2mqtt/data
cp -n zigbee2mqtt_data/configuration.yaml zigbee2mqtt/data/configuration.yaml
docker compose config --quiet
docker compose up -d
docker compose ps -a
docker compose logs --tail=80 mosquitto zigbee2mqtt
```

The copy seeds a fresh installation and leaves an existing runtime configuration in place. If you previously started this stack, keep the rest of `zigbee2mqtt/data/` with your network and pairing data. If the runtime configuration needs editing, stop Zigbee2MQTT first. Check that `mqtt.server` is `mqtt://mosquitto:1883`, that `frontend.enabled` and `homeassistant.enabled` are `true`, and that `serial.adapter` matches your coordinator. [Zigbee2MQTT configuration](https://www.zigbee2mqtt.io/guide/configuration/)

## Show a live temperature and its history

1. Open `http://<pi-ip>:8123` and finish Home Assistant setup. Under **Settings → Devices & services**, add **MQTT** with broker `127.0.0.1`, port `1883`, and blank credentials. If you already configured MQTT using the Pi's LAN address, reconfigure it to use `127.0.0.1`. [Home Assistant MQTT setup](https://www.home-assistant.io/integrations/mqtt.html)
2. Check the exact Hive model in the Zigbee2MQTT device guide before pairing. For example, the SLT3 reports battery, the SLT6b exposes measured temperature, and the SLR2d exposes measured temperature on its heating climate endpoint. For installed heating equipment, follow the model's pairing procedure. [Hive SLT3](https://www.zigbee2mqtt.io/devices/SLT3.html) · [Hive SLT6b](https://www.zigbee2mqtt.io/devices/SLT6b.html) · [Hive SLR2d](https://www.zigbee2mqtt.io/devices/SLR2d.html)
3. Open `http://<pi-ip>:8080`, use **Permit join** when the Hive device is ready to pair, and close joining after it appears. Check **Exposes** for the measured temperature. [Zigbee2MQTT pairing guide](https://www.zigbee2mqtt.io/guide/usage/pairing_devices.html)
4. Open the discovered MQTT device in Home Assistant. Add its temperature sensor or climate entity to the dashboard. Use **History** to select the entity once readings have accumulated. Home Assistant's built-in Recorder stores the history. [Home Assistant History](https://www.home-assistant.io/integrations/history/)

If Compose reports a device mapping error, check that the `.env` path still resolves to a character device on the Pi with `test -c /dev/serial/by-id/<your-device>` after replacing the placeholder. If the container starts and then exits, `docker compose logs --tail=80 zigbee2mqtt` shows whether it reached the adapter and the MQTT broker.

## Optional analytics

For a fresh InfluxDB setup, set `INFLUXDB_PASSWORD` and `INFLUXDB_ADMIN_TOKEN` in `.env`. Start the optional containers with `docker compose --profile analytics up -d influxdb grafana`. To use them for readings, configure the Home Assistant InfluxDB integration and add InfluxDB as a data source in Grafana. [Home Assistant InfluxDB integration](https://www.home-assistant.io/integrations/influxdb/) · [Grafana InfluxDB data source](https://grafana.com/docs/grafana/latest/datasources/influxdb/)

"""Arduino JSON-lines to Node-RED using the Python standard library only."""
import json
import logging
import math
import os
from pathlib import Path
import sys
import termios
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

LOG = logging.getLogger("edge-serial")
TOKEN = Path("/run/secrets/ingest_token")
OPENER = build_opener(ProxyHandler({}))  # This connection is Docker-local, never public.


def submit(reading, source="bme280"):
    body = json.dumps({"reading": reading, "source": source,
                       "sensor_id": os.getenv("SENSOR_ID", "arduino-bme280-01"),
                       "location": os.getenv("LOCATION", "indoor")}).encode()
    req = Request("http://nodered:1880/ingest", data=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + TOKEN.read_text().strip(),
    })
    with OPENER.open(req, timeout=10) as response:
        if response.status != 204:
            raise ValueError("Unexpected ingest response")


def serial_stream(device="/dev/arduino"):
    baud = int(os.getenv("SERIAL_BAUD", "9600"))
    speed = getattr(termios, "B" + str(baud), None)
    if speed is None:
        raise ValueError("Unsupported SERIAL_BAUD")
    with open(device, "r+b", buffering=0) as port:
        attr = termios.tcgetattr(port)
        attr[0] = termios.IGNPAR
        attr[1] = 0
        attr[2] = termios.CS8 | termios.CLOCAL | termios.CREAD
        attr[3] = 0
        attr[4] = attr[5] = speed
        attr[6][termios.VMIN] = 1
        attr[6][termios.VTIME] = 0
        termios.tcsetattr(port, termios.TCSANOW, attr)
        termios.tcflush(port, termios.TCIFLUSH)
        while True:
            line = port.readline(4097)
            if not line:
                raise OSError("Serial device disconnected")
            if len(line) > 4096:
                # Discard the remainder, not just the first fragment.
                while line and not line.endswith(b"\n"):
                    line = port.readline(4097)
                LOG.warning("oversized_serial_line_rejected")
                continue
            try:
                reading = json.loads(line)
                if not isinstance(reading, dict):
                    raise ValueError("Expected object")
            except (ValueError, UnicodeError):
                LOG.warning("invalid_serial_json_rejected")
                continue
            yield reading


def simulated_stream():
    index = 0
    while True:
        yield {"temperature": round(21 + math.sin(index / 10), 2),
               "humidity": 48.0, "pressure": 1013.25}
        index += 1
        time.sleep(5)


def main():
    simulate = len(sys.argv) > 1 and sys.argv[1] == "simulate"
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    while True:
        try:
            stream = simulated_stream() if simulate else serial_stream()
            for reading in stream:
                try:
                    submit(reading, "simulated" if simulate else "bme280")
                    LOG.info("reading_accepted source=%s", "simulated" if simulate else "bme280")
                except (URLError, TimeoutError, ValueError):
                    # Don't give a retried reading a misleading fresh measurement time.
                    LOG.warning("reading_not_stored; check Node-RED/Influx availability")
        except (OSError, ValueError):
            LOG.warning("serial_unavailable; reconnecting in five seconds")
            time.sleep(5)


if __name__ == "__main__":
    main()

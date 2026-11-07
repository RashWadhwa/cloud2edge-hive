# Move the prepared source files to your Pi

## Transfer without GitHub authentication

The bundle installer is implemented and tested, but this managed chat currently
opens its artifact links as HTML previews rather than delivering the ZIP. Do
not rename that HTML file to `.zip` or attempt to extract it. Until a supported
file-download channel is available, use the GitHub transfer route below. An
assistant upload requires permission if you previously reserved all pushes for
yourself; preparing a local source commit does not transfer it to GitHub or Pi.

If you obtain the actual ZIP through a working file-transfer channel:

Download the prepared `EdgeClimate-Pi.zip` bundle using the browser **on the Pi**.
It is an executable ZIP using Python's standard library, so extraction is not
necessary. Assuming the browser saved it under Downloads, run on the Pi:

```sh
python3 ~/Downloads/EdgeClimate-Pi.zip --target ~/cloud2edge-hive
```

The installer verifies every source file against the bundle's SHA-256 manifest,
backs up replaced source files under `~/edgeclimate-transfer-backups/`, and
copies the project into the existing checkout. Existing `.env`, `.edge`, Git
metadata, container data and unrelated files such as `get-docker.sh` are
preserved. The `.gitignore` runtime exclusion is merged into existing rules.
No GitHub token is required, no commit/push is performed, and services/firmware
are not changed by the transfer. A failed file-copy operation is rolled back.
An optional `--dry-run` lists planned changes without copying anything.

Then continue setup:

```sh
cd ~/cloud2edge-hive
./scripts/edge init
nano .edge/config.env
```

Set the known Arduino path:

```dotenv
ARDUINO_DEVICE=/dev/serial/by-id/usb-Arduino__www.arduino.cc__0043_7553334323635170D0F0-if00
```

Match `SERIAL_BAUD` to the actual working sketch. Close Serial Monitor before
starting the hardware collector. Follow [PROJECT.md](PROJECT.md) for the rest.

To rebuild a new bundle after source changes, from the cloud checkout:

```sh
python3 scripts/build-transfer.py --output /tmp/EdgeClimate-Pi.zip
```

This source-only bundle excludes runtime credentials, certificates and data.
The checksums detect transfer damage; they are not a digital signature. Download
the bundle only from the trusted chat handoff.

## Transfer through GitHub

The files were created in the shared cloud checkout, not remotely on your Pi.
The assistant has not committed or pushed them. Keep all pushes under your own
control. Review the changes first. From **this cloud checkout's terminal**:

```sh
cd /workspace/cloud2edge-hive
git status --short
git add .gitignore README.md compose.edge.yml edge scripts docs
git diff --cached --stat
git commit -m "Add secure Arduino edge monitoring with InfluxDB and Grafana"
git push origin HEAD:main
```

This pushes your current commit to `main` without force. If the remote has new
commits, reconcile them before retrying; do not force-push. Confirm the destination
branch complies with your repository's workflow. Never add `.edge/`, `.env`,
credentials, generated data or pairing files. Use `git diff --cached --name-only`
to check exactly which paths are staged.

Then, in the terminal **on your Pi**:

```sh
cd ~/cloud2edge-hive
git status --short --branch
git pull --ff-only
./scripts/edge init
ls -l /dev/serial/by-id/
nano .edge/config.env
```

Set the actual Arduino path and baud rate. The weather defaults to approximate
Wolverhampton coordinates. A full serial device listing includes `-> ...` after
the filename; leave that suffix out. The existing SONOFF stick is not the
Arduino. Follow [PROJECT.md](PROJECT.md) to configure the HTTPS certificate and
phone access, then run:

```sh
./scripts/edge up
./scripts/edge status
./scripts/edge verify
```

If the working Arduino sketch is not emitting the documented JSON-lines format,
send a few actual output lines before flashing the optional reference sketch.
For a clearly labelled software-only rehearsal, `./scripts/edge demo` needs no
Arduino. It does not validate physical sensing.

If a command fails, send the command and redacted error output. Do not send
password files, tokens, the contents of `.edge/secrets`, private keys or process
environment dumps.

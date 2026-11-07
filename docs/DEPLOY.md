# Deploy EdgeClimate on the Pi

The repository uses one branch, `main`, and one supported Arduino/BME280 stack
in `compose.edge.yml`. The temporary `codex/edgeclimate-transfer` branch is
retired after its contents are incorporated into main.

## Update the existing Pi checkout

Your Pi may have local commits such as `get-docker.sh` and a merge of the former
transfer branch. Merge the current main branch to preserve those commits:

```sh
cd ~/cloud2edge-hive
git status --short --branch
git pull --no-rebase origin main
git fetch --prune origin
```

If Git reports local edits or conflicts, resolve them before continuing. Do not
reset the checkout or force-push. An unused local copy of the temporary branch
can be deleted with `git branch -d codex/edgeclimate-transfer` once Git confirms
it is fully merged; it is not necessary to run the project.

Only the former tracked Hive/Zigbee service files are removed. Existing `.env`,
`.edge/`, container volumes, ignored runtime directories and unrelated files are
preserved. The source update does not stop or remove previously created
containers. Inspect `docker ps -a` and stop unused older services individually
if you wish; the current stack's container names start with `edgeclimate-`.

## Configure and run

```sh
./scripts/edge init
ls -l /dev/serial/by-id/
nano .edge/config.env
```

Init preserves existing local configuration and generated credentials. Set the
known Arduino path, without the `-> ../../ttyACM0` suffix from a directory listing:

```dotenv
ARDUINO_DEVICE=/dev/serial/by-id/usb-Arduino__www.arduino.cc__0043_7553334323635170D0F0-if00
```

Match `SERIAL_BAUD` to the working sketch's `Serial.begin(...)`. Close Serial
Monitor before starting the collector. If the Arduino is not emitting the
JSON-lines format in [PROJECT.md](PROJECT.md), check actual output before
flashing the optional reference sketch. IDE board selection is Arduino UNO;
the baud rate and physical readings still need verification.

Wolverhampton weather defaults are supplied. Follow the project guide to
configure the HTTPS certificate, Grafana access and phone hotspot connection.

```sh
./scripts/edge up
./scripts/edge status
./scripts/edge verify
```

For a clearly labelled software-only rehearsal without hardware, run
`./scripts/edge demo`. It does not validate physical sensing. Stopping/restarting
this stack preserves its named volumes.

## Future source changes

Review exactly what is staged before committing. Keep `.edge/`, `.env`, tokens,
private keys and generated data out of Git. Push from the machine containing
the actual source changes; updating GitHub does not update the Pi until it
pulls. Do not force-push over other commits.

If a command fails, send the command and redacted error output. Do not send
password files, tokens or process-environment dumps.

## Optional source bundle utility

`scripts/build-transfer.py` builds a verified, source-only ZIP for a working
file-transfer channel. The installer backs up replaced source files and
preserves local settings. This chat's artifact preview has not provided a
working ZIP download, so use the GitHub/main route above for this deployment.
Do not rename an HTML preview to `.zip`.

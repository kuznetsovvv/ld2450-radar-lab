# LD2450 Radar Lab

Experimental, dependency-free tools for turning coherent Hi-Link LD2450 frames
into stable tracks, manually configured origin/destination labels, and a
versioned configuration that a lightweight Home Assistant adapter can consume.

This project is the next stage of
[ESPHome LD2450 Atomic Frames](https://github.com/kuznetsovvv/esphome-ld2450-atomic-frame):
that project produces and optionally records coherent, device-timestamped radar
frames; this project replays, tracks, tunes, classifies, and deploys them.

## Get the data first

The lab does not reconstruct trajectories from separate Home Assistant X/Y
entities. Start with the atomic-frame project and choose a firmware path:

- **SCREEK Human Sensor 2A:** use its fuller
	[`examples/screek-2a/esp32-c3.yaml`](https://github.com/kuznetsovvv/esphome-ld2450-atomic-frame/blob/main/examples/screek-2a/esp32-c3.yaml)
	derivative. It retains the SCREEK parser, entities, software zones,
	illuminance, and PCB LED wiring while adding the atomic frame and related
	controls. Read the
	[SCREEK-specific setup and flash warnings](https://github.com/kuznetsovvv/esphome-ld2450-atomic-frame/blob/main/docs/screek-2a-derivative.md)
	first.
- **Other ESP32-C3 + LD2450 hardware:** include the portable
	[`packages/ld2450-atomic-frame.yaml`](https://github.com/kuznetsovvv/esphome-ld2450-atomic-frame/blob/main/packages/ld2450-atomic-frame.yaml)
	package, using the repository's minimal board example as a wiring/configuration
	starting point.

After flashing, Home Assistant receives one text sensor state per accepted radar
frame:

```text
t_ms|x1,y1,v1|x2,y2,v2|x3,y3,v3
```

The exact entity ID depends on the device name. The portable example defaults to
`sensor.ld2450_atomic_frame`; confirm yours in Developer Tools. Raw X/Y values
are millimetres and `t_ms` is ESP uptime, so the downstream tracker does not use
Home Assistant arrival timing for trajectory math.

### Record a CSV for the desktop lab

Install Pyscript, then copy the atomic-frame repository's
[`pyscript/apps/ld2450_atomic_logger/`](https://github.com/kuznetsovvv/esphome-ld2450-atomic-frame/tree/main/pyscript/apps/ld2450_atomic_logger)
directory to `/config/pyscript/apps/ld2450_atomic_logger/`. Merge its
[`pyscript/config.example.yaml`](https://github.com/kuznetsovvv/esphome-ld2450-atomic-frame/blob/main/pyscript/config.example.yaml)
under your existing `pyscript:` configuration and set `frame_entity` to the
actual entity ID.

The default output is `/config/ld2450_frames.csv`. Copy that private file to the
PC running this lab, start the lab, and click **Load atomic CSV**. The expected
logger schema is:

```text
wall_iso,t_ms,dt_ms,x1,y1,v1,x2,y2,v2,x3,y3,v3
```

The lab ignores the wall-clock column for tracking, handles 32-bit timestamp
rollover, and separates ESP reboot epochs. Uploads stay in server memory and are
not written into this repository. Treat the CSV as movement data and do not
publish it.

To experiment before installing firmware, click **Load example CSV** or load
[`examples/synthetic-atomic-frames.csv`](examples/synthetic-atomic-frames.csv)
manually. Its 44 deterministic rows contain four fictional routes:
`LEFT_HALL->ENTRY`, `ENTRY->RIGHT_HALL`, `LEFT_HALL->RIGHT_HALL`, and
`RIGHT_HALL->LEFT_HALL`. The final two run simultaneously: their identities
swap between densely packed slots 1 and 2, and observations are deliberately
omitted so association and coasting are visible. Solitary targets remain in
slot 1, matching observed LD2450 packing. The year-2000 wall clock and all
coordinates are synthetic.

### Use the same stream live in Home Assistant

After tuning portals and tracker values, click **Download config** and install
the adapter described in [docs/home-assistant.md](docs/home-assistant.md). The
adapter listens to the same atomic entity directly, loads the exported
`ld2450-radar-config/1`, and emits completed `ld2450-radar-event/1` O-D events.
You do not need the CSV logger for live operation.

## Status

Experimental prototype. The tracker core includes a
constant-velocity Kalman filter and exact global assignment for the LD2450's
maximum of three simultaneous detections. Synthetic tests deliberately swap
slot numbers and introduce observation gaps because LD2450 target slots are not
stable identities.

The browser lab now renders the LD2450's 120-degree forward field of view, raw
fixes, filtered tracks, and manual portals. Its View tab can rotate, mirror, and
pan the presentation, including a +90-degree side-looking preset. These mounting
controls are browser-local and never change tracker coordinates or exported
portal geometry.

The included Pyscript adapter consumes the same exported config and emits a
versioned O-D event plus an entity with confidence and reason attributes. It
uses Pyscript's local `modules/` support and does not require `allow_all_imports`.
See [docs/home-assistant.md](docs/home-assistant.md).

That deployment bridge belongs here because it implements these public schemas.
What happens after an O-D event does not: chimes, rich notifications, locks,
alarms, lights, and household-specific corroboration remain separate Home
Assistant policy.

Do not use this prototype for safety, security, or access control.

## Intended boundaries

- `ld2450_radar`: pure Python tracking, portal, classification, and bundle code
- browser lab: synthetic replay, visual tuning, and configuration export
- HA adapter example: consumes the exported contract without importing lab UI

Real captures, room geometry, entity IDs, notification targets, and household
rules are not part of this repository.

## Development

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\ld2450-radar-lab.exe
```

Open `http://127.0.0.1:8765`. The bundled scenario is synthetic; real captures
and room geometry should remain outside the repository. Uploads are capped at
25 MB / 250,000 rows. At minimum, CSV input must contain `t_ms` and all three
`xN,yN,vN` slot groups; logger metadata columns are optional.

## Home Assistant

See [docs/home-assistant.md](docs/home-assistant.md). The adapter targets Home
Assistant Core 2026.8.2 and Pyscript 2.1.0 as its current compatibility baseline.
It includes no notification target or household automation. A small event-driven
Logbook example shows the intended boundary.

## Contracts

- `ld2450-radar-config/1`: tracker values, classifier values, units, and portals
- `ld2450-radar-event/1`: completed O-D label, confidence, reason, span, and count

Breaking changes require a new schema name. Browser mounting transforms are
view-only and never enter either contract.
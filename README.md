# LD2450 Radar Lab

Experimental, dependency-free tools for turning coherent Hi-Link LD2450 frames
into stable tracks, manually configured origin/destination labels, and a
versioned configuration that a lightweight Home Assistant adapter can consume.

This project is the planned follow-up to
[ESPHome LD2450 Atomic Frames](https://github.com/kuznetsovvv/esphome-ld2450-atomic-frame).

## Status

Private review prototype. The tracker core includes a
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
and room geometry should remain outside the repository. Use **Load atomic CSV**
to inspect a logger export from the atomic-frame project. Uploads are parsed into
memory, are capped at 25 MB / 250,000 rows, and are never written by the lab.

The required CSV columns are:

```text
t_ms,x1,y1,v1,x2,y2,v2,x3,y3,v3
```

Additional logger columns such as `wall_iso` and `dt_ms` are accepted. ESP reboot
discontinuities become separate tracking epochs; 32-bit `millis()` rollover stays
continuous.

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
# Home Assistant adapter

The browser lab exports `ld2450-radar-config/1`. The included Pyscript adapter
loads that file, consumes the atomic text sensor, reconstructs slot-independent
tracks, and emits one `ld2450-radar-event/1` event when a confirmed track ends.

This is deliberately a thin deployment boundary. The adapter does not contain
notification targets, chime entities, household geometry, door logic, or ghost
cues. Automations consume its stable event contract.

## Requirements

- Home Assistant with the Pyscript custom integration
- the atomic-frame sensor from
  [esphome-ld2450-atomic-frame](https://github.com/kuznetsovvv/esphome-ld2450-atomic-frame)
- Pyscript 2.1 or later

The adapter works with Pyscript's default import sandbox. It does not require
`allow_all_imports` or a third-party Python package installation.

## Install

1. Copy `ha/pyscript/modules/ld2450_radar_runtime.py` to
   `/config/pyscript/modules/ld2450_radar_runtime.py`.
2. Copy `ha/pyscript/apps/ld2450_radar/` to
   `/config/pyscript/apps/ld2450_radar/`.
3. Download the lab configuration and store it as
   `/config/pyscript/ld2450-radar-config.json`.
4. Merge `ha/pyscript/config.example.yaml` into the existing `pyscript:`
   configuration.
5. Reload Pyscript.

The default frame entity is `sensor.ld2450_atomic_frame`. Override it in the app
configuration when Home Assistant assigned a different entity ID.

Use the `pyscript.ld2450_radar_reload` service after replacing the JSON config.
The app publishes readiness or configuration errors through
`pyscript.ld2450_radar_event`.

## Verify before automating

1. Confirm `pyscript.ld2450_radar_event` reports `ready` and its
   `config_schema` attribute is `ld2450-radar-config/1`.
2. Open Developer Tools > Events and subscribe to `ld2450_radar_event`.
3. Walk one complete route between two configured portals, then stop or leave
   the field long enough for `max_coast_s` to expire.
4. Inspect the event's `label`, `confidence`, `reason`, `span_mm`, and
   `point_count`. Repeat both directions and deliberately walk outside a portal;
   the latter should report low confidence rather than silently guessing.
5. Add `ha/pyscript/automation.example.yaml` only after the observed events match
   the intended geometry.

Start with Logbook or a dashboard entity. Add chimes, mobile notifications, or
other side effects later, with their own cooldowns and confidence conditions.

## Update and rollback

Downloading config does not deploy it automatically:

1. Keep the last known-good JSON file.
2. Replace `/config/pyscript/ld2450-radar-config.json` with the newly downloaded
   file.
3. Call `pyscript.ld2450_radar_reload`.
4. Confirm the event entity returns to `ready`, then repeat one known route.

If validation or live behavior is wrong, restore the previous JSON and call the
same reload service. No Home Assistant restart is required. The app constructs a
new runtime on reload, so active partial tracks are discarded rather than mixed
across configurations.

To remove the adapter, disable dependent automations, remove its app entry and
files, then reload Pyscript. The atomic-frame producer and optional CSV logger
are independent and can remain installed.

## Event contract

Each completed track fires `ld2450_radar_event` and updates the configured event
entity. Event data includes:

```yaml
schema: ld2450-radar-event/1
observed_at: "2026-01-01T12:00:00.000+00:00"
track_id: 7
origin: LEFT_HALL
destination: ENTRY
label: LEFT_HALL->ENTRY
confidence: medium
reason: endpoint_portals
span_mm: 1834.2
point_count: 14
```

Version 1 confidence is intentionally conservative:

- `medium`: exactly one origin and destination portal matched
- `low / unmatched_endpoint`: an endpoint matched no portal
- `low / overlapping_portals`: an endpoint matched multiple portals
- `low / short_track`: endpoint span was below the configured floor

The example automation logs non-low-confidence events. Chimes, mobile
notifications, lights, alarms, occupancy state, and cross-sensor corroboration
belong in separate automations. Do not put those actions inside the tracker.

The adapter belongs in this repository because it is the executable consumer of
the exported config and event schema. Site policy does not: notification text,
quiet hours, people, locks, alarms, lights, and escalation rules should live in
the user's private Home Assistant configuration or in separate generic recipes.

## Operational notes

- The adapter flushes a track after the configured coast interval passes without
  a new atomic frame. Device timestamp rollover is continuous; ESP reboot flushes
  active tracks and starts a new clock epoch.
- Portal and tracker values use millimetres and seconds. Browser rotation, mirror,
  and pan are view-only and are not exported.
- Atomic frames and trajectory events can reveal movement patterns. Keep real
  config files, captures, and automation history private.
- This remains experimental software. Treat low-confidence and missing events as
  expected failure modes, and do not use it alone for safety or access control.
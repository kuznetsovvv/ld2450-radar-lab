# pyright: reportUndefinedVariable=false

import datetime
import json
import time

from ld2450_radar_runtime import flush_runtime, make_runtime, process_payload

APP_CONFIG = pyscript.app_config
FRAME_ENTITY = str(APP_CONFIG.get("frame_entity", "sensor.ld2450_atomic_frame"))
CONFIG_PATH = str(APP_CONFIG.get("config_path", "/config/pyscript/ld2450-radar-config.json"))
EVENT_ENTITY = str(APP_CONFIG.get("event_entity", "pyscript.ld2450_radar_event"))
EVENT_NAME = str(APP_CONFIG.get("event_name", "ld2450_radar_event"))

_runtime = None
_last_frame_wall = 0.0
_sequence = 0
_frame_trigger_refs = []


if not FRAME_ENTITY.startswith("sensor."):
    raise ValueError("frame_entity must be in the sensor domain")
if not CONFIG_PATH.startswith("/config/") or "/../" in CONFIG_PATH:
    raise ValueError("config_path must be an absolute path below /config")
if not EVENT_ENTITY.startswith("pyscript."):
    raise ValueError("event_entity must be in the pyscript domain")


@pyscript_executor
def _read_config(path):
    with open(path, encoding="utf-8") as source:
        return json.load(source)


def _publish(events):
    global _sequence
    for item in events:
        _sequence += 1
        value = item.copy()
        value["observed_at"] = datetime.datetime.now().astimezone().isoformat(
            timespec="milliseconds"
        )
        state.set(EVENT_ENTITY, str(_sequence) + ":" + value["label"], value)
        event.fire(EVENT_NAME, **value)


def _reload_config():
    global _runtime
    config = _read_config(CONFIG_PATH)
    _runtime = make_runtime(config)
    state.set(
        EVENT_ENTITY,
        "ready",
        {"schema": "ld2450-radar-event/1", "config_schema": config["schema"]},
    )


@time_trigger("startup")
def load_ld2450_radar():
    try:
        _reload_config()
    except Exception as error:
        log.error("failed to load LD2450 radar config: " + str(error))
        state.set(EVENT_ENTITY, "config_error", {"reason": str(error)})


@service
def ld2450_radar_reload():
    """Reload the exported LD2450 radar configuration."""
    _reload_config()


def _install_frame_trigger(entity_id):
    @state_trigger(entity_id)
    def on_atomic_frame(value=None, **kwargs):
        global _last_frame_wall
        _ = kwargs
        if _runtime is None or value in (None, "unknown", "unavailable"):
            return
        try:
            completed, clock_reset = process_payload(_runtime, value)
            _last_frame_wall = time.time()
            if clock_reset:
                log.warning("LD2450 device clock reset; active tracks were flushed")
            _publish(completed)
        except Exception as error:
            log.error("invalid LD2450 atomic frame: " + str(error))

    return on_atomic_frame


_frame_trigger_refs.append(_install_frame_trigger(FRAME_ENTITY))


@time_trigger("period(now, 500ms)")
def flush_idle_tracks():
    global _last_frame_wall
    if _runtime is None or _last_frame_wall <= 0:
        return
    max_coast_s = _runtime["config"]["tracker"]["max_coast_s"]
    if time.time() - _last_frame_wall > max_coast_s:
        _publish(flush_runtime(_runtime))
        _last_frame_wall = 0.0


@time_trigger("shutdown")
def flush_tracks_on_shutdown():
    if _runtime is not None:
        _publish(flush_runtime(_runtime))
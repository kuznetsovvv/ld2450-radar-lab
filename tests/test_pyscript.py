import importlib.util
import json
import pathlib
import sys
import types
import unittest

from ld2450_radar import classify_track, default_config, demo_frames, track_frames


ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNTIME_PATH = ROOT / "ha" / "pyscript" / "modules" / "ld2450_radar_runtime.py"
APP_PATH = ROOT / "ha" / "pyscript" / "apps" / "ld2450_radar" / "__init__.py"


def load_runtime():
    spec = importlib.util.spec_from_file_location("ld2450_radar_runtime", RUNTIME_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def frame_payload(frame):
    slots = [[0, 0, 0] for _ in range(3)]
    for detection in frame.detections:
        slots[detection.slot - 1] = [round(detection.x_mm), round(detection.y_mm), 0]
    return str(round(frame.t_s * 1000)) + "|" + "|".join(
        ",".join(str(value) for value in slot) for slot in slots
    )


def passthrough_decorator(*_args, **_kwargs):
    def decorate(function):
        return function

    return decorate


class StateStub:
    def __init__(self):
        self.values = []

    def set(self, entity_id, value, attributes):
        self.values.append((entity_id, value, attributes))


class EventStub:
    def __init__(self):
        self.values = []

    def fire(self, name, **data):
        self.values.append((name, data))


class LogStub:
    def error(self, _message):
        pass

    def warning(self, _message):
        pass


class PyscriptRuntimeTests(unittest.TestCase):
    def test_sandbox_runtime_matches_standard_core_labels(self):
        module = load_runtime()
        config = default_config()
        expected = sorted(
            classify_track(track, config.portals, config.classifier).label
            for track in track_frames(demo_frames(), config.tracker)
        )
        runtime = module.make_runtime(config.to_dict())
        actual = []
        for frame in demo_frames():
            completed, _reset = module.process_payload(runtime, frame_payload(frame))
            actual.extend(item["label"] for item in completed)
        actual.extend(item["label"] for item in module.flush_runtime(runtime))

        self.assertEqual(sorted(actual), expected)

    def test_app_publishes_entity_and_event_contract(self):
        module = load_runtime()
        sys.modules["ld2450_radar_runtime"] = module
        state = StateStub()
        event = EventStub()
        namespace = {
            "pyscript": types.SimpleNamespace(
                app_config={
                    "frame_entity": "sensor.test_atomic_frame",
                    "config_path": "/config/pyscript/test-radar-config.json",
                    "event_entity": "pyscript.test_radar_event",
                    "event_name": "test_radar_event",
                }
            ),
            "state_trigger": passthrough_decorator,
            "time_trigger": passthrough_decorator,
            "service": passthrough_decorator,
            "pyscript_executor": lambda function: function,
            "state": state,
            "event": event,
            "log": LogStub(),
        }
        source = APP_PATH.read_text(encoding="utf-8")
        exec(compile(source, str(APP_PATH), "exec"), namespace)
        namespace["_read_config"] = lambda _path: default_config().to_dict()
        namespace["load_ld2450_radar"]()
        trigger = namespace["_frame_trigger_refs"][0]
        for frame in demo_frames()[:15]:
            trigger(value=frame_payload(frame))
        namespace["flush_tracks_on_shutdown"]()

        published = [item for item in state.values if item[1] not in ("ready", "config_error")]
        self.assertEqual(len(published), 1)
        self.assertEqual(published[0][2]["schema"], "ld2450-radar-event/1")
        self.assertEqual(event.values[0][0], "test_radar_event")
        self.assertEqual(event.values[0][1]["label"], "LEFT_HALL->ENTRY")

    def test_idle_flush_only_runs_once_without_another_frame(self):
        module = load_runtime()
        sys.modules["ld2450_radar_runtime"] = module
        namespace = {
            "pyscript": types.SimpleNamespace(app_config={}),
            "state_trigger": passthrough_decorator,
            "time_trigger": passthrough_decorator,
            "service": passthrough_decorator,
            "pyscript_executor": lambda function: function,
            "state": StateStub(),
            "event": EventStub(),
            "log": LogStub(),
        }
        source = APP_PATH.read_text(encoding="utf-8")
        exec(compile(source, str(APP_PATH), "exec"), namespace)
        namespace["_read_config"] = lambda _path: default_config().to_dict()
        namespace["load_ld2450_radar"]()
        namespace["_last_frame_wall"] = 1.0
        namespace["time"] = types.SimpleNamespace(time=lambda: 100.0)

        namespace["flush_idle_tracks"]()
        namespace["flush_idle_tracks"]()

        self.assertEqual(namespace["_last_frame_wall"], 0.0)


if __name__ == "__main__":
    unittest.main()
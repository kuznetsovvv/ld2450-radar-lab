import json
import tempfile
import unittest
from pathlib import Path

from ld2450_radar import (
    BoxPortal,
    ClassifierConfig,
    Track,
    TrackPoint,
    classify_track,
    default_config,
    demo_frames,
    load_config,
    save_config,
    track_frames,
)


class PortalAndContractTests(unittest.TestCase):
    def test_default_config_round_trips_as_versioned_json(self):
        config = default_config()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "radar-config.json"
            save_config(config, path)
            loaded = load_config(path)

        self.assertEqual(loaded, config)
        self.assertEqual(config.to_dict()["schema"], "ld2450-radar-config/1")

    def test_rejects_unknown_config_version(self):
        value = default_config().to_dict()
        value["schema"] = "ld2450-radar-config/99"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "radar-config.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unsupported config schema"):
                load_config(path)

    def test_overlapping_portals_produce_an_explicit_low_confidence_reason(self):
        track = Track(
            4,
            [
                TrackPoint(0, 0, 0, 0, 0, 0, 0, 1),
                TrackPoint(1, 1000, 0, 1000, 0, 1000, 0, 2),
            ],
            confirmed=True,
        )
        portals = (
            BoxPortal("A", -10, 100, -10, 100),
            BoxPortal("B", -20, 200, -20, 200),
            BoxPortal("C", 900, 1100, -100, 100),
        )
        result = classify_track(track, portals, ClassifierConfig(endpoint_points=1))

        self.assertEqual(result.reason, "overlapping_portals")
        self.assertEqual(result.confidence, "low")
        self.assertIsNone(result.origin)

    def test_synthetic_walks_track_and_label_end_to_end(self):
        config = default_config()
        tracks = track_frames(demo_frames(), config.tracker)
        labels = [classify_track(track, config.portals, config.classifier).label for track in tracks]

        self.assertEqual(
            sorted(labels),
            sorted(
                [
                    "LEFT_HALL->ENTRY",
                    "ENTRY->RIGHT_HALL",
                    "LEFT_HALL->RIGHT_HALL",
                    "RIGHT_HALL->LEFT_HALL",
                ]
            ),
        )


if __name__ == "__main__":
    unittest.main()
import json
import pathlib
import unittest

from ld2450_radar import RadarConfig, demo_csv_text


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ArtifactTests(unittest.TestCase):
    def test_example_json_is_the_supported_contract(self):
        value = json.loads(
            (ROOT / "ha" / "pyscript" / "ld2450-radar-config.example.json").read_text(
                encoding="utf-8"
            )
        )
        config = RadarConfig.from_dict(value)

        self.assertEqual(config.to_dict(), value)

    def test_pyscript_config_has_expected_app_and_safe_defaults(self):
        text = (ROOT / "ha" / "pyscript" / "config.example.yaml").read_text(
            encoding="utf-8"
        )

        self.assertIn("apps:\n  ld2450_radar:", text)
        self.assertIn("frame_entity: sensor.ld2450_atomic_frame", text)
        self.assertNotIn("allow_all_imports", text)

    def test_automation_uses_current_event_and_action_shape(self):
        text = (ROOT / "ha" / "pyscript" / "automation.example.yaml").read_text(
            encoding="utf-8"
        )

        self.assertIn("triggers:\n    - trigger: event", text)
        self.assertIn("event_type: ld2450_radar_event", text)
        self.assertIn("actions:\n    - action: logbook.log", text)
        self.assertEqual(text.count("    - action:"), 1)

    def test_pyscript_runtime_imports_only_default_allowed_module(self):
        source = (
            ROOT / "ha" / "pyscript" / "modules" / "ld2450_radar_runtime.py"
        ).read_text(encoding="utf-8")

        imports = [line for line in source.splitlines() if line.startswith("import ")]
        self.assertEqual(imports, ["import math"])

    def test_ha_guide_covers_verification_and_rollback(self):
        text = (ROOT / "docs" / "home-assistant.md").read_text(encoding="utf-8")

        self.assertIn("## Verify before automating", text)
        self.assertIn("subscribe to `ld2450_radar_event`", text)
        self.assertIn("## Update and rollback", text)
        self.assertIn("restore the previous JSON", text)

    def test_downloadable_csv_fixture_matches_the_generator(self):
        example = (ROOT / "examples" / "synthetic-atomic-frames.csv").read_text(
            encoding="utf-8"
        )

        self.assertEqual(demo_csv_text().splitlines(), example.splitlines())


if __name__ == "__main__":
    unittest.main()
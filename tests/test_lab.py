import json
import threading
import unittest
from urllib.request import Request, urlopen

from ld2450_radar.lab import evaluate_config, serve
from ld2450_radar.synthetic import default_config


class LabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = serve(port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_state_endpoint_runs_synthetic_pipeline(self):
        with urlopen(f"{self.base_url}/api/state") as response:
            value = json.load(response)

        self.assertEqual(value["config"]["schema"], "ld2450-radar-config/1")
        self.assertEqual(value["summary"]["track_count"], 4)
        self.assertEqual(value["summary"]["classified_count"], 4)

    def test_config_endpoint_validates_and_re_evaluates(self):
        config = default_config().to_dict()
        config["tracker"]["gate_mm"] = 525
        request = Request(
            f"{self.base_url}/api/config",
            data=json.dumps(config).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request) as response:
            value = json.load(response)

        self.assertEqual(value["config"]["tracker"]["gate_mm"], 525)

    def test_static_assets_are_served(self):
        for path, expected in (
            ("/", b"Mounting view"),
            ("/app.js", b"view-range"),
            ("/styles.css", b".fov-wedge"),
            ("/synthetic-atomic-frames.csv", b"wall_iso,t_ms,dt_ms"),
        ):
            with urlopen(f"{self.base_url}{path}") as response:
                self.assertIn(expected, response.read())

    def test_atomic_csv_upload_stays_in_memory_and_reports_reboot_epochs(self):
        content = (
            "wall_iso,t_ms,dt_ms,x1,y1,v1,x2,y2,v2,x3,y3,v3\n"
            "2026-01-01T00:00:00Z,100,,0,500,0,0,0,0,0,0,0\n"
            "2026-01-01T00:00:00Z,200,100,100,500,0,0,0,0,0,0,0\n"
            "2026-01-01T00:00:01Z,10,,900,500,0,0,0,0,0,0,0\n"
            "2026-01-01T00:00:01Z,110,100,1000,500,0,0,0,0,0,0,0\n"
        ).encode()
        request = Request(
            f"{self.base_url}/api/frames",
            data=content,
            headers={"Content-Type": "text/csv", "X-File-Name": "private-walk.csv"},
            method="POST",
        )
        with urlopen(request) as response:
            value = json.load(response)

        self.assertEqual(value["summary"]["source_name"], "private-walk.csv")
        self.assertEqual(value["summary"]["frame_count"], 4)
        self.assertEqual(value["summary"]["epoch_count"], 2)

        demo_request = Request(f"{self.base_url}/api/demo", data=b"demo", method="POST")
        with urlopen(demo_request) as response:
            demo = json.load(response)
        self.assertEqual(demo["summary"]["source_name"], "Synthetic demo")


if __name__ == "__main__":
    unittest.main()
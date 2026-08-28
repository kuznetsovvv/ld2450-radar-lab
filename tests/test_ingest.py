import pathlib
import unittest

from ld2450_radar import classify_track, default_config, parse_atomic_csv, track_frames


HEADER = "t_ms,x1,y1,v1,x2,y2,v2,x3,y3,v3\n"
ROOT = pathlib.Path(__file__).resolve().parents[1]


class IngestTests(unittest.TestCase):
    def test_reboot_starts_a_new_epoch(self):
        dataset = parse_atomic_csv(
            HEADER
            + "500000,1,2,0,0,0,0,0,0,0\n"
            + "500100,2,3,0,0,0,0,0,0,0\n"
            + "10000,3,4,0,0,0,0,0,0,0\n"
        )

        self.assertEqual(dataset.row_count, 3)
        self.assertEqual([len(epoch) for epoch in dataset.epochs], [2, 1])

    def test_missing_atomic_column_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing columns: v3"):
            parse_atomic_csv("t_ms,x1,y1,v1,x2,y2,v2,x3,y3\n1,1,1,0,0,0,0,0,0\n")

    def test_committed_fixture_reproduces_all_default_routes(self):
        path = ROOT / "examples" / "synthetic-atomic-frames.csv"
        dataset = parse_atomic_csv(path.read_text(encoding="utf-8"))
        config = default_config()
        tracks = []
        for epoch in dataset.epochs:
            tracks.extend(track_frames(list(epoch), config.tracker))
        labels = sorted(
            classify_track(track, config.portals, config.classifier).label
            for track in tracks
        )

        self.assertEqual(dataset.row_count, 44)
        self.assertEqual(
            labels,
            sorted(
                [
                    "ENTRY->RIGHT_HALL",
                    "LEFT_HALL->ENTRY",
                    "LEFT_HALL->RIGHT_HALL",
                    "RIGHT_HALL->LEFT_HALL",
                ]
            ),
        )

    def test_demo_frames_use_dense_slots_and_swap_multi_target_identity(self):
        from ld2450_radar import demo_frames

        frames = demo_frames()
        for frame in frames:
            self.assertEqual(
                [detection.slot for detection in frame.detections],
                list(range(1, len(frame.detections) + 1)),
            )
        two_target_frames = [frame for frame in frames if len(frame.detections) == 2]
        first_slot_x = [frame.detections[0].x_mm for frame in two_target_frames]
        self.assertTrue(any(x_mm < 0 for x_mm in first_slot_x))
        self.assertTrue(any(x_mm > 0 for x_mm in first_slot_x))


if __name__ == "__main__":
    unittest.main()
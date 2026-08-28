import unittest

from ld2450_radar import Detection, Frame, TrackerConfig, track_frames


class TrackerTests(unittest.TestCase):
    def test_crossing_targets_keep_identity_across_slot_swaps_and_gap(self):
        frames = []
        for index in range(13):
            t_s = index * 0.2
            detections = []
            if index not in (6, 7):
                detections.append(Detection(-1200 + index * 200, 900, 1 if index % 2 else 2))
            detections.append(Detection(1200 - index * 200, 1250, 2 if index % 2 else 1))
            frames.append(Frame(t_s, tuple(reversed(detections)) if index % 3 == 0 else tuple(detections)))

        tracks = track_frames(
            frames,
            TrackerConfig(gate_mm=650, max_coast_s=0.6, min_confirmed_hits=3),
        )

        self.assertEqual(len(tracks), 2)
        lower = min(tracks, key=lambda track: track.points[0].observed_y_mm)
        upper = max(tracks, key=lambda track: track.points[0].observed_y_mm)
        self.assertLess(lower.points[0].observed_x_mm, 0)
        self.assertGreater(lower.points[-1].observed_x_mm, 0)
        self.assertGreater(upper.points[0].observed_x_mm, 0)
        self.assertLess(upper.points[-1].observed_x_mm, 0)
        self.assertGreater(len({point.source_slot for point in lower.points}), 1)


if __name__ == "__main__":
    unittest.main()
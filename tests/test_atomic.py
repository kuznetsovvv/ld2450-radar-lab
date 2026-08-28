import unittest

from ld2450_radar import AtomicFrameDecoder, StreamingTracker, TrackerConfig


class AtomicFrameTests(unittest.TestCase):
    def test_decoder_ignores_empty_slots_and_preserves_slot_number(self):
        decoded = AtomicFrameDecoder().decode("1234|10,20,3|0,0,0|-40,50,-2")

        self.assertFalse(decoded.clock_reset)
        self.assertEqual(decoded.frame.t_s, 1.234)
        self.assertEqual([item.slot for item in decoded.frame.detections], [1, 3])

    def test_decoder_distinguishes_rollover_from_reboot(self):
        decoder = AtomicFrameDecoder()
        decoder.decode("4294967280|1,1,0|0,0,0|0,0,0")
        rollover = decoder.decode("32|2,2,0|0,0,0|0,0,0")
        reboot = decoder.decode("10|3,3,0|0,0,0|0,0,0")

        self.assertFalse(rollover.clock_reset)
        self.assertAlmostEqual(rollover.frame.t_s, (2**32 + 32) / 1000)
        self.assertTrue(reboot.clock_reset)
        self.assertEqual(reboot.frame.t_s, 0.01)

    def test_streaming_tracker_flushes_tracks_across_idle_gap(self):
        decoder = AtomicFrameDecoder()
        tracker = StreamingTracker(TrackerConfig(min_confirmed_hits=2, max_coast_s=0.3))
        completed = []
        for payload in (
            "0|0,500,0|0,0,0|0,0,0",
            "100|100,500,0|0,0,0|0,0,0",
            "500|900,500,0|0,0,0|0,0,0",
            "600|1000,500,0|0,0,0|0,0,0",
        ):
            completed.extend(tracker.update(decoder.decode(payload).frame))
        completed.extend(tracker.flush())

        self.assertEqual(len(completed), 2)
        self.assertEqual([len(track.points) for track in completed], [2, 2])


if __name__ == "__main__":
    unittest.main()
import unittest

from ld2450_radar import parse_atomic_csv


HEADER = "t_ms,x1,y1,v1,x2,y2,v2,x3,y3,v3\n"


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


if __name__ == "__main__":
    unittest.main()
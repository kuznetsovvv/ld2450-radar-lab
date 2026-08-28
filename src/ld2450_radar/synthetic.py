from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
from random import Random

from .classification import ClassifierConfig
from .contract import RadarConfig
from .model import Detection, Frame
from .portals import BoxPortal, SectorPortal
from .tracker import TrackerConfig


def default_config() -> RadarConfig:
    return RadarConfig(
        tracker=TrackerConfig(),
        classifier=ClassifierConfig(),
        portals=(
            BoxPortal("ENTRY", -350, 350, 150, 650),
            SectorPortal("LEFT_HALL", 1200, 2400, -58, -30, -58, -30),
            SectorPortal("RIGHT_HALL", 1200, 2400, 30, 58, 30, 58),
        ),
    )


def demo_frames(seed: int = 7) -> list[Frame]:
    random = Random(seed)
    paths = (
        (0.0, (-1650.0, 1500.0), (0.0, 400.0), {7}),
        (4.5, (0.0, 400.0), (1650.0, 1500.0), set()),
        (9.0, (-1650.0, 1500.0), (1650.0, 1500.0), {5, 6}),
        (9.0, (1650.0, 1050.0), (-1650.0, 1050.0), {8, 9}),
    )
    by_time: dict[float, list[tuple[int, float, float]]] = {}
    for path_index, (start_t, start, end, missing) in enumerate(paths):
        points = 15
        for index in range(points):
            if index in missing:
                continue
            fraction = index / (points - 1)
            x_mm = start[0] + fraction * (end[0] - start[0]) + random.gauss(0, 28)
            y_mm = start[1] + fraction * (end[1] - start[1]) + random.gauss(0, 28)
            t_s = round(start_t + index * 0.2, 6)
            by_time.setdefault(t_s, []).append((path_index, x_mm, y_mm))

    frames = []
    for frame_index, (t_s, observations) in enumerate(sorted(by_time.items())):
        ordered = sorted(observations)
        if frame_index % 2:
            ordered.reverse()
        detections = tuple(
            Detection(x_mm, y_mm, slot)
            for slot, (_path_index, x_mm, y_mm) in enumerate(ordered, start=1)
        )
        frames.append(Frame(t_s, detections))
    return frames


def demo_csv_text(seed: int = 7) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        ("wall_iso", "t_ms", "dt_ms", "x1", "y1", "v1", "x2", "y2", "v2", "x3", "y3", "v3")
    )
    base = datetime(2000, 1, 1, tzinfo=timezone.utc)
    previous_t_ms = None
    for frame in demo_frames(seed):
        t_ms = round(frame.t_s * 1000)
        slots = [[0, 0, 0] for _ in range(3)]
        for detection in frame.detections:
            slots[detection.slot - 1] = [
                round(detection.x_mm),
                round(detection.y_mm),
                0,
            ]
        wall_iso = (base + timedelta(milliseconds=t_ms)).isoformat(timespec="milliseconds")
        delta = "" if previous_t_ms is None else t_ms - previous_t_ms
        writer.writerow((wall_iso, t_ms, delta, *(value for slot in slots for value in slot)))
        previous_t_ms = t_ms
    return output.getvalue()
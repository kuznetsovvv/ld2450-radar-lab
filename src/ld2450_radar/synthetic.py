from __future__ import annotations

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
    )
    by_time: dict[float, list[Detection]] = {}
    for path_index, (start_t, start, end, missing) in enumerate(paths):
        points = 15
        for index in range(points):
            if index in missing:
                continue
            fraction = index / (points - 1)
            x_mm = start[0] + fraction * (end[0] - start[0]) + random.gauss(0, 28)
            y_mm = start[1] + fraction * (end[1] - start[1]) + random.gauss(0, 28)
            t_s = round(start_t + index * 0.2, 6)
            slot = 1 + (path_index + index) % 3
            by_time.setdefault(t_s, []).append(Detection(x_mm, y_mm, slot))
    return [Frame(t_s, tuple(detections)) for t_s, detections in sorted(by_time.items())]
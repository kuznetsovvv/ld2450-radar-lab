from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Detection:
    x_mm: float
    y_mm: float
    slot: int

    def __post_init__(self) -> None:
        if self.slot not in (1, 2, 3):
            raise ValueError("slot must be 1, 2, or 3")


@dataclass(frozen=True)
class Frame:
    t_s: float
    detections: tuple[Detection, ...]

    def __post_init__(self) -> None:
        if len(self.detections) > 3:
            raise ValueError("an LD2450 frame can contain at most three detections")


@dataclass(frozen=True)
class TrackPoint:
    t_s: float
    observed_x_mm: float
    observed_y_mm: float
    filtered_x_mm: float
    filtered_y_mm: float
    velocity_x_mm_s: float
    velocity_y_mm_s: float
    source_slot: int


@dataclass
class Track:
    id: int
    points: list[TrackPoint] = field(default_factory=list)
    confirmed: bool = False

    @property
    def first_t_s(self) -> float:
        return self.points[0].t_s

    @property
    def last_t_s(self) -> float:
        return self.points[-1].t_s
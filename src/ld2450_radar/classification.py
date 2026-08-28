from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from statistics import median

from .model import Track
from .portals import Portal, matching_portals


@dataclass(frozen=True)
class ClassifierConfig:
    endpoint_points: int = 3
    min_span_mm: float = 500.0

    def __post_init__(self) -> None:
        if self.endpoint_points < 1:
            raise ValueError("endpoint_points must be at least one")
        if self.min_span_mm < 0:
            raise ValueError("min_span_mm cannot be negative")


@dataclass(frozen=True)
class ODResult:
    track_id: int
    origin: str | None
    destination: str | None
    label: str
    confidence: str
    reason: str
    span_mm: float
    point_count: int

    def to_event(self, observed_at: str) -> dict[str, object]:
        return {
            "schema": "ld2450-radar-event/1",
            "observed_at": observed_at,
            "track_id": self.track_id,
            "origin": self.origin,
            "destination": self.destination,
            "label": self.label,
            "confidence": self.confidence,
            "reason": self.reason,
            "span_mm": round(self.span_mm, 1),
            "point_count": self.point_count,
        }


def classify_track(
    track: Track,
    portals: tuple[Portal, ...],
    config: ClassifierConfig | None = None,
) -> ODResult:
    config = config or ClassifierConfig()
    if not track.points:
        raise ValueError("cannot classify an empty track")

    count = min(config.endpoint_points, len(track.points))
    start = track.points[:count]
    end = track.points[-count:]
    start_x = median(point.filtered_x_mm for point in start)
    start_y = median(point.filtered_y_mm for point in start)
    end_x = median(point.filtered_x_mm for point in end)
    end_y = median(point.filtered_y_mm for point in end)
    span_mm = hypot(end_x - start_x, end_y - start_y)
    origin_matches = matching_portals(start_x, start_y, portals)
    destination_matches = matching_portals(end_x, end_y, portals)
    origin = origin_matches[0] if len(origin_matches) == 1 else None
    destination = destination_matches[0] if len(destination_matches) == 1 else None

    if span_mm < config.min_span_mm:
        confidence, reason = "low", "short_track"
    elif len(origin_matches) > 1 or len(destination_matches) > 1:
        confidence, reason = "low", "overlapping_portals"
    elif origin is None or destination is None:
        confidence, reason = "low", "unmatched_endpoint"
    else:
        confidence, reason = "medium", "endpoint_portals"

    label = f"{origin or 'UNKNOWN'}->{destination or 'UNKNOWN'}"
    return ODResult(
        track_id=track.id,
        origin=origin,
        destination=destination,
        label=label,
        confidence=confidence,
        reason=reason,
        span_mm=span_mm,
        point_count=len(track.points),
    )
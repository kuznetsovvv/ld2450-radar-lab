from __future__ import annotations

from dataclasses import dataclass
from math import hypot

from .kalman import ConstantVelocityFilter
from .model import Detection, Frame, Track, TrackPoint

_TIME_EPSILON_S = 1e-9


@dataclass(frozen=True)
class TrackerConfig:
    gate_mm: float = 700.0
    max_coast_s: float = 1.25
    measurement_sigma_mm: float = 120.0
    acceleration_sigma_mm_s2: float = 900.0
    initial_position_sigma_mm: float = 250.0
    initial_velocity_sigma_mm_s: float = 1400.0
    min_confirmed_hits: int = 3


@dataclass
class _LiveTrack:
    public: Track
    filter: ConstantVelocityFilter
    state_t_s: float
    last_seen_t_s: float


def _best_assignment(
    tracks: list[_LiveTrack], detections: tuple[Detection, ...], gate_mm: float
) -> list[tuple[int, int]]:
    best_cost = float("inf")
    best_pairs: list[tuple[int, int]] = []
    unmatched_cost = gate_mm

    def visit(
        detection_index: int,
        used_tracks: set[int],
        pairs: list[tuple[int, int]],
        cost: float,
    ) -> None:
        nonlocal best_cost, best_pairs
        if cost >= best_cost:
            return
        if detection_index == len(detections):
            best_cost = cost
            best_pairs = list(pairs)
            return

        visit(detection_index + 1, used_tracks, pairs, cost + unmatched_cost)
        detection = detections[detection_index]
        for track_index, track in enumerate(tracks):
            if track_index in used_tracks:
                continue
            x_mm, y_mm, _, _ = track.filter.state
            distance = hypot(detection.x_mm - x_mm, detection.y_mm - y_mm)
            if distance >= gate_mm:
                continue
            used_tracks.add(track_index)
            pairs.append((track_index, detection_index))
            visit(detection_index + 1, used_tracks, pairs, cost + distance)
            pairs.pop()
            used_tracks.remove(track_index)

    visit(0, set(), [], 0.0)
    return best_pairs


class StreamingTracker:
    def __init__(self, config: TrackerConfig | None = None) -> None:
        self.config = config or TrackerConfig()
        self._live: list[_LiveTrack] = []
        self._next_id = 0
        self._previous_t_s: float | None = None

    def update(self, frame: Frame) -> list[Track]:
        config = self.config
        if self._previous_t_s is not None and frame.t_s <= self._previous_t_s:
            raise ValueError("frame timestamps must be strictly increasing")
        self._previous_t_s = frame.t_s

        completed = []
        still_live = []
        for track in self._live:
            if frame.t_s - track.last_seen_t_s <= config.max_coast_s + _TIME_EPSILON_S:
                dt_s = frame.t_s - track.state_t_s
                track.filter.predict(dt_s, config.acceleration_sigma_mm_s2**2)
                track.state_t_s = frame.t_s
                still_live.append(track)
            else:
                if track.public.confirmed:
                    completed.append(track.public)
        self._live = still_live

        pairs = _best_assignment(self._live, frame.detections, config.gate_mm)
        matched_detections = {detection_index for _, detection_index in pairs}
        measurement_variance = config.measurement_sigma_mm**2

        for track_index, detection_index in pairs:
            track = self._live[track_index]
            detection = frame.detections[detection_index]
            track.filter.update(detection.x_mm, detection.y_mm, measurement_variance)
            x_mm, y_mm, velocity_x, velocity_y = track.filter.state
            track.public.points.append(
                TrackPoint(
                    frame.t_s,
                    detection.x_mm,
                    detection.y_mm,
                    x_mm,
                    y_mm,
                    velocity_x,
                    velocity_y,
                    detection.slot,
                )
            )
            track.last_seen_t_s = frame.t_s
            track.public.confirmed = len(track.public.points) >= config.min_confirmed_hits

        for detection_index, detection in enumerate(frame.detections):
            if detection_index in matched_detections:
                continue
            public = Track(id=self._next_id)
            kalman = ConstantVelocityFilter(
                detection.x_mm,
                detection.y_mm,
                config.initial_position_sigma_mm**2,
                config.initial_velocity_sigma_mm_s**2,
            )
            public.points.append(
                TrackPoint(
                    frame.t_s,
                    detection.x_mm,
                    detection.y_mm,
                    detection.x_mm,
                    detection.y_mm,
                    0.0,
                    0.0,
                    detection.slot,
                )
            )
            public.confirmed = config.min_confirmed_hits <= 1
            self._live.append(_LiveTrack(public, kalman, frame.t_s, frame.t_s))
            self._next_id += 1

        return completed

    def flush(self) -> list[Track]:
        completed = [track.public for track in self._live if track.public.confirmed]
        self._live = []
        self._previous_t_s = None
        return completed


def track_frames(frames: list[Frame], config: TrackerConfig | None = None) -> list[Track]:
    tracker = StreamingTracker(config)
    finished = []
    for frame in sorted(frames, key=lambda item: item.t_s):
        finished.extend(tracker.update(frame))
    finished.extend(tracker.flush())
    return finished
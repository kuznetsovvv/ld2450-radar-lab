from __future__ import annotations

from dataclasses import dataclass

from .model import Detection, Frame

UINT32_MODULUS = 1 << 32
ROLLOVER_HIGH_WATER = 0xF0000000
ROLLOVER_LOW_WATER = 0x0FFFFFFF


@dataclass(frozen=True)
class DecodedFrame:
    frame: Frame
    clock_reset: bool


def parse_atomic_payload(payload: str) -> tuple[int, tuple[Detection, ...]]:
    if not isinstance(payload, str):
        raise TypeError("payload must be a string")
    parts = payload.split("|")
    if len(parts) != 4:
        raise ValueError("payload must contain one timestamp and three target slots")
    try:
        t_ms = int(parts[0])
    except ValueError as error:
        raise ValueError("timestamp must be an integer") from error
    if not 0 <= t_ms < UINT32_MODULUS:
        raise ValueError("timestamp must be an unsigned 32-bit value")

    detections = []
    for slot, segment in enumerate(parts[1:], start=1):
        values = segment.split(",")
        if len(values) != 3:
            raise ValueError(f"target slot {slot} must contain x,y,v")
        try:
            x_mm, y_mm, _speed_raw = (int(value) for value in values)
        except ValueError as error:
            raise ValueError(f"target slot {slot} contains a non-integer") from error
        if x_mm != 0 or y_mm != 0:
            detections.append(Detection(x_mm, y_mm, slot))
    return t_ms, tuple(detections)


class AtomicFrameDecoder:
    def __init__(self) -> None:
        self._previous_t_ms: int | None = None
        self._rollover_offset_ms = 0

    def decode(self, payload: str) -> DecodedFrame:
        t_ms, detections = parse_atomic_payload(payload)
        clock_reset = False
        if self._previous_t_ms is not None and t_ms < self._previous_t_ms:
            if (
                self._previous_t_ms >= ROLLOVER_HIGH_WATER
                and t_ms <= ROLLOVER_LOW_WATER
            ):
                self._rollover_offset_ms += UINT32_MODULUS
            else:
                self._rollover_offset_ms = 0
                clock_reset = True
        self._previous_t_ms = t_ms
        return DecodedFrame(
            Frame((self._rollover_offset_ms + t_ms) / 1000.0, detections),
            clock_reset,
        )
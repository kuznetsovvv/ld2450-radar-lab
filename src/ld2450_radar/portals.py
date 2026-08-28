from __future__ import annotations

from dataclasses import dataclass
from math import atan2, degrees, hypot
from typing import Any


@dataclass(frozen=True)
class BoxPortal:
    name: str
    min_x_mm: float
    max_x_mm: float
    min_y_mm: float
    max_y_mm: float

    def __post_init__(self) -> None:
        _validate_name(self.name)
        if self.min_x_mm >= self.max_x_mm or self.min_y_mm >= self.max_y_mm:
            raise ValueError(f"box portal {self.name!r} must have increasing bounds")

    def contains(self, x_mm: float, y_mm: float) -> bool:
        return (
            self.min_x_mm <= x_mm <= self.max_x_mm
            and self.min_y_mm <= y_mm <= self.max_y_mm
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "shape": "box",
            "min_x_mm": self.min_x_mm,
            "max_x_mm": self.max_x_mm,
            "min_y_mm": self.min_y_mm,
            "max_y_mm": self.max_y_mm,
        }


@dataclass(frozen=True)
class SectorPortal:
    name: str
    min_range_mm: float
    max_range_mm: float
    near_min_angle_deg: float
    near_max_angle_deg: float
    far_min_angle_deg: float
    far_max_angle_deg: float

    def __post_init__(self) -> None:
        _validate_name(self.name)
        if self.min_range_mm < 0 or self.min_range_mm >= self.max_range_mm:
            raise ValueError(f"sector portal {self.name!r} must have increasing ranges")
        if self.near_min_angle_deg >= self.near_max_angle_deg:
            raise ValueError(f"sector portal {self.name!r} has invalid near angles")
        if self.far_min_angle_deg >= self.far_max_angle_deg:
            raise ValueError(f"sector portal {self.name!r} has invalid far angles")

    def contains(self, x_mm: float, y_mm: float) -> bool:
        range_mm = hypot(x_mm, y_mm)
        if not self.min_range_mm <= range_mm <= self.max_range_mm:
            return False
        fraction = (range_mm - self.min_range_mm) / (
            self.max_range_mm - self.min_range_mm
        )
        min_angle = self.near_min_angle_deg + fraction * (
            self.far_min_angle_deg - self.near_min_angle_deg
        )
        max_angle = self.near_max_angle_deg + fraction * (
            self.far_max_angle_deg - self.near_max_angle_deg
        )
        angle = degrees(atan2(x_mm, y_mm))
        return min_angle <= angle <= max_angle

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "shape": "sector",
            "min_range_mm": self.min_range_mm,
            "max_range_mm": self.max_range_mm,
            "near_min_angle_deg": self.near_min_angle_deg,
            "near_max_angle_deg": self.near_max_angle_deg,
            "far_min_angle_deg": self.far_min_angle_deg,
            "far_max_angle_deg": self.far_max_angle_deg,
        }


Portal = BoxPortal | SectorPortal


def portal_from_dict(value: dict[str, Any]) -> Portal:
    shape = value.get("shape")
    if shape == "box":
        return BoxPortal(
            name=str(value["name"]),
            min_x_mm=float(value["min_x_mm"]),
            max_x_mm=float(value["max_x_mm"]),
            min_y_mm=float(value["min_y_mm"]),
            max_y_mm=float(value["max_y_mm"]),
        )
    if shape == "sector":
        return SectorPortal(
            name=str(value["name"]),
            min_range_mm=float(value["min_range_mm"]),
            max_range_mm=float(value["max_range_mm"]),
            near_min_angle_deg=float(value["near_min_angle_deg"]),
            near_max_angle_deg=float(value["near_max_angle_deg"]),
            far_min_angle_deg=float(value["far_min_angle_deg"]),
            far_max_angle_deg=float(value["far_max_angle_deg"]),
        )
    raise ValueError(f"unsupported portal shape: {shape!r}")


def matching_portals(
    x_mm: float, y_mm: float, portals: tuple[Portal, ...]
) -> tuple[str, ...]:
    return tuple(portal.name for portal in portals if portal.contains(x_mm, y_mm))


def validate_portals(portals: tuple[Portal, ...]) -> None:
    names = [portal.name for portal in portals]
    if len(names) != len(set(names)):
        raise ValueError("portal names must be unique")


def _validate_name(name: str) -> None:
    if not name or not name.replace("_", "").isalnum():
        raise ValueError("portal names must contain only letters, numbers, and underscores")
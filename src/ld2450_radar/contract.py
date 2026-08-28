from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .classification import ClassifierConfig
from .portals import Portal, portal_from_dict, validate_portals
from .tracker import TrackerConfig

CONFIG_SCHEMA = "ld2450-radar-config/1"


@dataclass(frozen=True)
class RadarConfig:
    tracker: TrackerConfig
    classifier: ClassifierConfig
    portals: tuple[Portal, ...]
    schema: str = CONFIG_SCHEMA
    coordinate_units: str = "mm"
    time_units: str = "s"

    def __post_init__(self) -> None:
        if self.schema != CONFIG_SCHEMA:
            raise ValueError(f"unsupported config schema: {self.schema!r}")
        if self.coordinate_units != "mm" or self.time_units != "s":
            raise ValueError("version 1 requires millimetres and seconds")
        validate_portals(self.portals)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "coordinate_units": self.coordinate_units,
            "time_units": self.time_units,
            "tracker": asdict(self.tracker),
            "classifier": asdict(self.classifier),
            "portals": [portal.to_dict() for portal in self.portals],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RadarConfig":
        if value.get("schema") != CONFIG_SCHEMA:
            raise ValueError(f"unsupported config schema: {value.get('schema')!r}")
        return cls(
            schema=str(value["schema"]),
            coordinate_units=str(value.get("coordinate_units", "")),
            time_units=str(value.get("time_units", "")),
            tracker=TrackerConfig(**value["tracker"]),
            classifier=ClassifierConfig(**value["classifier"]),
            portals=tuple(portal_from_dict(item) for item in value["portals"]),
        )


def save_config(config: RadarConfig, path: str | Path) -> None:
    Path(path).write_text(
        json.dumps(config.to_dict(), indent=2) + "\n", encoding="utf-8"
    )


def load_config(path: str | Path) -> RadarConfig:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("config root must be an object")
    return RadarConfig.from_dict(value)
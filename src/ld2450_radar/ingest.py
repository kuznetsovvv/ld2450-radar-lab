from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from .atomic import AtomicFrameDecoder
from .model import Frame

REQUIRED_COLUMNS = tuple(
    f"{field}{slot}" for slot in (1, 2, 3) for field in ("x", "y", "v")
)


@dataclass(frozen=True)
class AtomicDataset:
    epochs: tuple[tuple[Frame, ...], ...]
    row_count: int


def parse_atomic_csv(text: str, max_rows: int = 250_000) -> AtomicDataset:
    reader = csv.DictReader(io.StringIO(text))
    headers = set(reader.fieldnames or ())
    missing = [name for name in ("t_ms", *REQUIRED_COLUMNS) if name not in headers]
    if missing:
        raise ValueError("atomic CSV is missing columns: " + ", ".join(missing))

    decoder = AtomicFrameDecoder()
    epochs: list[list[Frame]] = [[]]
    row_count = 0
    for row_number, row in enumerate(reader, start=2):
        if row_count >= max_rows:
            raise ValueError(f"atomic CSV exceeds the {max_rows:,}-row limit")
        try:
            payload = str(row["t_ms"]) + "|" + "|".join(
                ",".join(str(row[f"{field}{slot}"]) for field in ("x", "y", "v"))
                for slot in (1, 2, 3)
            )
            decoded = decoder.decode(payload)
        except (TypeError, ValueError) as error:
            raise ValueError(f"invalid atomic CSV row {row_number}: {error}") from error

        if decoded.clock_reset and epochs[-1]:
            epochs.append([])
        if epochs[-1] and decoded.frame.t_s <= epochs[-1][-1].t_s:
            raise ValueError(f"atomic CSV row {row_number} has a duplicate timestamp")
        epochs[-1].append(decoded.frame)
        row_count += 1

    populated = tuple(tuple(epoch) for epoch in epochs if epoch)
    if not populated:
        raise ValueError("atomic CSV contains no data rows")
    return AtomicDataset(populated, row_count)
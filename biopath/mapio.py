"""Map loading and representation."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable, List, Tuple


@dataclass(frozen=True)
class GridMap:
    name: str
    cell_size_m: float
    ascii: List[str]
    height: int
    width: int
    walkable: List[List[bool]]
    walkable_count: int
    weights: List[List[float]]
    weight_total: float
    weights_provided: bool

    def in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.height and 0 <= col < self.width

    def is_walkable(self, row: int, col: int) -> bool:
        return self.walkable[row][col]

    def iter_walkable(self) -> Iterable[Tuple[int, int]]:
        for row in range(self.height):
            for col in range(self.width):
                if self.walkable[row][col]:
                    yield row, col

    def neighbors4(self, row: int, col: int) -> Iterable[Tuple[int, int]]:
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = row + dr, col + dc
            if self.in_bounds(nr, nc):
                yield nr, nc


def _parse_ascii(rows: List[str]) -> Tuple[int, int, List[List[bool]], int]:
    if not rows:
        raise ValueError("ascii grid must be non-empty")
    width = len(rows[0])
    if width == 0:
        raise ValueError("ascii grid must have non-empty rows")
    height = len(rows)
    walkable: List[List[bool]] = [[False for _ in range(width)] for _ in range(height)]
    walkable_count = 0
    for r, row in enumerate(rows):
        if len(row) != width:
            raise ValueError("all ascii rows must be the same length")
        for c, ch in enumerate(row):
            if ch == ".":
                walkable[r][c] = True
                walkable_count += 1
            elif ch == "#":
                continue
            else:
                raise ValueError("ascii grid may only contain '.' or '#'")
    return height, width, walkable, walkable_count


def _parse_weights(
    rows: List[str],
    walkable: List[List[bool]],
    weight_rows: object,
) -> Tuple[List[List[float]], float, bool]:
    height = len(rows)
    width = len(rows[0]) if rows else 0
    weights: List[List[float]] = [[0.0 for _ in range(width)] for _ in range(height)]
    total = 0.0

    if weight_rows is None:
        for r in range(height):
            for c in range(width):
                if walkable[r][c]:
                    weights[r][c] = 1.0
                    total += 1.0
        return weights, total, False

    if not isinstance(weight_rows, list) or not all(isinstance(r, list) for r in weight_rows):
        raise ValueError("weights must be a list of lists")
    if len(weight_rows) != height:
        raise ValueError("weights must match ascii height")
    for r, row in enumerate(weight_rows):
        if len(row) != width:
            raise ValueError("weights must match ascii width")
        for c, value in enumerate(row):
            if walkable[r][c]:
                if not isinstance(value, (int, float)):
                    raise ValueError("weights must be numeric for walkable cells")
                if value < 0:
                    raise ValueError("weights must be >= 0")
                weights[r][c] = float(value)
                total += weights[r][c]
            else:
                if value is None or value == 0:
                    continue
                if isinstance(value, (int, float)) and value > 0:
                    raise ValueError("weights for obstacles must be 0")
                raise ValueError("weights for obstacles must be 0 or null")
    return weights, total, True


def load_map_data(data: dict) -> GridMap:
    """Load a GridMap from a parsed JSON dict."""
    name = data.get("name")
    cell_size_m = data.get("cell_size_m")
    rows = data.get("ascii")
    weights_raw = data.get("weights")
    if not isinstance(name, str):
        raise ValueError("name must be a string")
    if not isinstance(cell_size_m, (int, float)):
        raise ValueError("cell_size_m must be a number")
    if not isinstance(rows, list) or not all(isinstance(r, str) for r in rows):
        raise ValueError("ascii must be a list of strings")
    height, width, walkable, walkable_count = _parse_ascii(rows)
    weights, weight_total, weights_provided = _parse_weights(rows, walkable, weights_raw)
    return GridMap(
        name=name,
        cell_size_m=float(cell_size_m),
        ascii=rows,
        height=height,
        width=width,
        walkable=walkable,
        walkable_count=walkable_count,
        weights=weights,
        weight_total=weight_total,
        weights_provided=weights_provided,
    )


def load_map(path: str | Path) -> GridMap:
    """Load a GridMap from a JSON file."""
    path = Path(path)
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError("map JSON must be an object")
    return load_map_data(data)

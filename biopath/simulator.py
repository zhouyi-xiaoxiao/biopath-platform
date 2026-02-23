"""Simulation utilities for BioPath."""

from __future__ import annotations

from typing import Iterable, Tuple

from .mapio import GridMap
from .objective import objective_with_distance_map


def simulate(
    grid_map: GridMap, traps: Iterable[Tuple[int, int]]
) -> tuple[float, list[list[float | None]]]:
    """Compute objective and distance map for a set of traps."""
    return objective_with_distance_map(grid_map, traps)

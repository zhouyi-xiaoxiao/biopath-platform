"""Candidate trap selection rules."""

from __future__ import annotations

from typing import List, Tuple

from .mapio import GridMap


def all_walkable(grid_map: GridMap) -> List[Tuple[int, int]]:
    """Return every walkable cell as a candidate."""
    return list(grid_map.iter_walkable())


def adjacent_to_wall(grid_map: GridMap, min_wall_neighbors: int = 1) -> List[Tuple[int, int]]:
    """Return walkable cells with at least min_wall_neighbors walls nearby."""
    if min_wall_neighbors < 0:
        raise ValueError("min_wall_neighbors must be >= 0")
    candidates: List[Tuple[int, int]] = []
    for row, col in grid_map.iter_walkable():
        wall_neighbors = 0
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = row + dr, col + dc
            if not grid_map.in_bounds(nr, nc):
                wall_neighbors += 1
            elif not grid_map.is_walkable(nr, nc):
                wall_neighbors += 1
        if wall_neighbors >= min_wall_neighbors:
            candidates.append((row, col))
    return candidates

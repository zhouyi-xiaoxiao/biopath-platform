"""Objective functions for trap placement."""

from __future__ import annotations

from collections import deque
import math
from math import isinf
from typing import Iterable, List, Tuple

from .mapio import GridMap


def compute_distance_map(
    grid_map: GridMap, traps: Iterable[Tuple[int, int]]
) -> List[List[float | None]]:
    """Compute multi-source BFS distances to the nearest trap in meters."""
    distance: List[List[float | None]] = []
    for row in range(grid_map.height):
        row_dist: List[float | None] = []
        for col in range(grid_map.width):
            if grid_map.is_walkable(row, col):
                row_dist.append(float("inf"))
            else:
                row_dist.append(None)
        distance.append(row_dist)
    trap_list = list(traps)
    if not trap_list:
        return distance

    queue: deque[Tuple[int, int]] = deque()
    for row, col in trap_list:
        if not grid_map.in_bounds(row, col):
            raise ValueError("trap coordinate out of bounds")
        if not grid_map.is_walkable(row, col):
            raise ValueError("trap must be on a walkable cell")
        if distance[row][col] != 0.0:
            distance[row][col] = 0.0
            queue.append((row, col))

    while queue:
        row, col = queue.popleft()
        current = distance[row][col]
        if current is None:
            continue
        for nr, nc in grid_map.neighbors4(row, col):
            if not grid_map.is_walkable(nr, nc):
                continue
            if distance[nr][nc] == float("inf"):
                distance[nr][nc] = current + grid_map.cell_size_m
                queue.append((nr, nc))
    return distance


def mean_distance_to_traps(grid_map: GridMap, traps: Iterable[Tuple[int, int]]) -> float:
    """Return the mean distance from walkable cells to the nearest trap."""
    distance = compute_distance_map(grid_map, traps)
    if grid_map.walkable_count == 0:
        return 0.0
    total = 0.0
    count = 0
    for row in range(grid_map.height):
        for col in range(grid_map.width):
            if not grid_map.is_walkable(row, col):
                continue
            value = distance[row][col]
            if value is None or isinf(value):
                return float("inf")
            total += value
            count += 1
    return total / count if count else 0.0


def weighted_mean_distance_to_traps(
    grid_map: GridMap, traps: Iterable[Tuple[int, int]]
) -> float:
    """Return the weighted mean distance from walkable cells to the nearest trap."""
    distance = compute_distance_map(grid_map, traps)
    if grid_map.weight_total == 0:
        return 0.0
    total = 0.0
    weight_total = 0.0
    for row in range(grid_map.height):
        for col in range(grid_map.width):
            if not grid_map.is_walkable(row, col):
                continue
            weight = grid_map.weights[row][col]
            if weight <= 0:
                continue
            value = distance[row][col]
            if value is None or isinf(value):
                return float("inf")
            total += weight * value
            weight_total += weight
    return total / weight_total if weight_total else 0.0


def distance_metrics(
    grid_map: GridMap,
    distance_map: List[List[float | None]],
    coverage_radius_m: float | None = None,
) -> dict[str, float | None]:
    """Compute summary metrics for a distance map."""
    values: List[float] = []
    has_inf = False
    total = 0.0
    count = 0

    weighted_total = 0.0
    weighted_weight = 0.0
    weighted_has_inf = False

    for row in range(grid_map.height):
        for col in range(grid_map.width):
            if not grid_map.is_walkable(row, col):
                continue
            value = distance_map[row][col]
            if value is None:
                continue
            if isinf(value):
                has_inf = True
            else:
                values.append(value)
                total += value
                count += 1

            weight = grid_map.weights[row][col]
            if weight > 0:
                weighted_weight += weight
                if isinf(value):
                    weighted_has_inf = True
                else:
                    weighted_total += weight * value

    mean_distance = float("inf") if has_inf else (total / count if count else 0.0)
    weighted_mean_distance = (
        float("inf")
        if weighted_has_inf
        else (weighted_total / weighted_weight if weighted_weight else 0.0)
    )
    max_distance = float("inf") if has_inf else (max(values) if values else 0.0)
    p95_distance = float("inf") if has_inf else _percentile(values, 0.95)

    metrics: dict[str, float | None] = {
        "mean_distance_m": mean_distance,
        "weighted_mean_distance_m": weighted_mean_distance,
        "max_distance_m": max_distance,
        "p95_distance_m": p95_distance,
        "coverage_within_radius": None,
        "weighted_coverage_within_radius": None,
    }

    if coverage_radius_m is not None:
        covered = 0
        covered_weight = 0.0
        for row in range(grid_map.height):
            for col in range(grid_map.width):
                if not grid_map.is_walkable(row, col):
                    continue
                value = distance_map[row][col]
                if value is None or isinf(value):
                    continue
                if value <= coverage_radius_m:
                    covered += 1
                    covered_weight += grid_map.weights[row][col]
        coverage = covered / grid_map.walkable_count if grid_map.walkable_count else 0.0
        weighted_coverage = (
            covered_weight / weighted_weight if weighted_weight else 0.0
        )
        metrics["coverage_within_radius"] = coverage
        metrics["weighted_coverage_within_radius"] = weighted_coverage

    return metrics


def _percentile(values: List[float], fraction: float) -> float:
    if not values:
        return 0.0
    fraction = min(max(fraction, 0.0), 1.0)
    sorted_values = sorted(values)
    idx = max(0, min(len(sorted_values) - 1, math.ceil(fraction * len(sorted_values)) - 1))
    return sorted_values[idx]


def objective_with_distance_map(
    grid_map: GridMap, traps: Iterable[Tuple[int, int]]
) -> Tuple[float, List[List[float | None]]]:
    distance = compute_distance_map(grid_map, traps)
    if grid_map.walkable_count == 0:
        return 0.0, distance
    total = 0.0
    count = 0
    for row in range(grid_map.height):
        for col in range(grid_map.width):
            if not grid_map.is_walkable(row, col):
                continue
            value = distance[row][col]
            if value is None or isinf(value):
                return float("inf"), distance
            total += value
            count += 1
    return (total / count if count else 0.0), distance

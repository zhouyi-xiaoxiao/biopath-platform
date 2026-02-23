"""Capture probability estimators for BioPath."""

from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Iterable, Sequence, Tuple

from .mapio import GridMap

Trap = Tuple[int, int]


@dataclass
class CaptureEstimate:
    capture_probability: float
    expected_time_to_capture: float
    ci95_low: float
    ci95_high: float


@dataclass
class RobustCaptureEstimate:
    robust_score: float
    scenario_scores: list[dict[str, float | str]]


def _normal_ci(p: float, n: int) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 0.0
    sigma = math.sqrt(max(p * (1.0 - p), 0.0) / n)
    margin = 1.96 * sigma
    return max(0.0, p - margin), min(1.0, p + margin)


def _mix_seed(seed: int, run_index: int) -> int:
    """Deterministically derive an independent per-run seed.

    Using a per-run RNG removes cross-run coupling: an early capture in run i no
    longer changes the random stream used by run i+1. This makes candidate
    comparison for capture-based objectives more stable.
    """
    mask = (1 << 64) - 1
    x = (int(seed) + 0x9E3779B97F4A7C15 * (run_index + 1)) & mask
    x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9 & mask
    x = (x ^ (x >> 27)) * 0x94D049BB133111EB & mask
    x = x ^ (x >> 31)
    return x


def _choose_start(
    grid_map: GridMap,
    rng: random.Random,
    entry_points: Sequence[tuple[int, int, float]] | None = None,
    *,
    walkables: Sequence[tuple[int, int]] | None = None,
) -> tuple[int, int]:
    if entry_points:
        weighted = [ep for ep in entry_points if ep[2] > 0 and grid_map.is_walkable(ep[0], ep[1])]
        if weighted:
            total = sum(w for _, _, w in weighted)
            pick = rng.random() * total
            acc = 0.0
            for row, col, weight in weighted:
                acc += weight
                if pick <= acc:
                    return row, col
    if walkables is None:
        walkables = list(grid_map.iter_walkable())
    if not walkables:
        return 0, 0
    if grid_map.weights_provided and grid_map.weight_total > 0:
        total = grid_map.weight_total
        pick = rng.random() * total
        acc = 0.0
        for row, col in walkables:
            acc += grid_map.weights[row][col]
            if pick <= acc:
                return row, col
    return walkables[rng.randrange(len(walkables))]


def _step(
    grid_map: GridMap,
    row: int,
    col: int,
    rng: random.Random,
    movement_model: str,
    bias: tuple[float, float],
) -> tuple[int, int]:
    neighbors = [xy for xy in grid_map.neighbors4(row, col) if grid_map.is_walkable(xy[0], xy[1])]
    if not neighbors:
        return row, col

    bx, by = bias
    model = movement_model.lower()
    lazy_prob = 0.25 if model == "lazy" else 0.0
    if model == "biased":
        lazy_prob = 0.1

    if rng.random() < lazy_prob:
        return row, col

    if model != "biased":
        return neighbors[rng.randrange(len(neighbors))]

    scores: list[float] = []
    for nr, nc in neighbors:
        dx = nc - col
        dy = nr - row
        score = 1.0 + (bx * dx) + (by * dy)
        scores.append(max(score, 0.05))

    total = sum(scores)
    pick = rng.random() * total
    acc = 0.0
    for (nr, nc), score in zip(neighbors, scores):
        acc += score
        if pick <= acc:
            return nr, nc
    return neighbors[-1]


def _walkable_degree(grid_map: GridMap, row: int, col: int) -> int:
    return sum(1 for nr, nc in grid_map.neighbors4(row, col) if grid_map.is_walkable(nr, nc))


def _sparse_entry_points(grid_map: GridMap) -> list[tuple[int, int, float]]:
    """Build an entry-point distribution that stresses sparse-map bottlenecks."""
    walkables = list(grid_map.iter_walkable())
    if not walkables:
        return []

    degree_sum = 0
    dead_end_count = 0
    low_degree: list[tuple[int, int, float]] = []

    for row, col in walkables:
        degree = _walkable_degree(grid_map, row, col)
        degree_sum += degree
        if degree <= 1:
            dead_end_count += 1
        if degree <= 2:
            # Dead-ends and corridors are common failure modes on sparse maps.
            weight = 2.2 if degree <= 1 else 1.4
            if grid_map.weights_provided:
                weight *= max(1.0, grid_map.weights[row][col])
            low_degree.append((row, col, weight))

    avg_degree = degree_sum / len(walkables)
    dead_end_ratio = dead_end_count / len(walkables)
    low_degree_ratio = len(low_degree) / len(walkables)

    sparse_like = avg_degree <= 2.15 or dead_end_ratio >= 0.10 or low_degree_ratio >= 0.55
    if not sparse_like or not low_degree:
        return []

    # Cap to keep runtime flat while remaining deterministic.
    max_points = min(64, max(12, len(low_degree)))
    low_degree.sort(key=lambda item: (-item[2], item[0], item[1]))
    selected = low_degree[:max_points]
    return selected


def simulate_capture_probability(
    grid_map: GridMap,
    traps: Iterable[Trap],
    *,
    mc_runs: int = 120,
    time_horizon_steps: int = 40,
    seed: int = 0,
    movement_model: str = "lazy",
    entry_points: Sequence[tuple[int, int, float]] | None = None,
    bias: tuple[float, float] = (0.0, 0.0),
) -> CaptureEstimate:
    trap_set = set(traps)
    horizon = max(1, int(time_horizon_steps))
    runs = max(1, int(mc_runs))
    walkables = list(grid_map.iter_walkable())

    if not trap_set or not walkables:
        return CaptureEstimate(0.0, float(horizon), 0.0, 0.0)

    captures = 0
    total_time = 0.0

    for run_index in range(runs):
        run_rng = random.Random(_mix_seed(seed, run_index))
        row, col = _choose_start(
            grid_map,
            run_rng,
            entry_points=entry_points,
            walkables=walkables,
        )

        captured = False
        for t in range(1, horizon + 1):
            if (row, col) in trap_set:
                captures += 1
                total_time += t
                captured = True
                break
            row, col = _step(
                grid_map,
                row,
                col,
                run_rng,
                movement_model=movement_model,
                bias=bias,
            )
        if not captured:
            total_time += float(horizon)

    p = captures / runs
    ci_low, ci_high = _normal_ci(p, runs)
    return CaptureEstimate(
        capture_probability=p,
        expected_time_to_capture=total_time / runs,
        ci95_low=ci_low,
        ci95_high=ci_high,
    )


def robust_capture_score(
    grid_map: GridMap,
    traps: Iterable[Trap],
    *,
    mc_runs: int = 120,
    time_horizon_steps: int = 40,
    seed: int = 0,
) -> RobustCaptureEstimate:
    sparse_entries = _sparse_entry_points(grid_map)

    scenarios: list[tuple[str, str, tuple[float, float], int, Sequence[tuple[int, int, float]] | None]] = [
        ("lazy_neutral", "lazy", (0.0, 0.0), seed + 11, None),
        ("biased_right", "biased", (0.5, 0.0), seed + 29, None),
    ]
    if sparse_entries:
        scenarios.append(("sparse_stress", "lazy", (0.0, 0.0), seed + 53, sparse_entries))
    else:
        scenarios.append(("biased_down", "biased", (0.0, 0.5), seed + 53, None))

    scenario_scores: list[dict[str, float | str]] = []
    score_values: list[float] = []

    for name, model, bias, s, entry_points in scenarios:
        est = simulate_capture_probability(
            grid_map,
            traps,
            mc_runs=mc_runs,
            time_horizon_steps=time_horizon_steps,
            seed=s,
            movement_model=model,
            entry_points=entry_points,
            bias=bias,
        )
        score_values.append(est.capture_probability)
        scenario_scores.append(
            {
                "name": name,
                "capture_probability": est.capture_probability,
                "expected_time_to_capture": est.expected_time_to_capture,
                "ci95_low": est.ci95_low,
                "ci95_high": est.ci95_high,
            }
        )

    robust = min(score_values) if score_values else 0.0
    return RobustCaptureEstimate(robust_score=robust, scenario_scores=scenario_scores)

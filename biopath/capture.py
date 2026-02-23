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
    scenario_scores: list[dict[str, float]]


def _normal_ci(p: float, n: int) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 0.0
    sigma = math.sqrt(max(p * (1.0 - p), 0.0) / n)
    margin = 1.96 * sigma
    return max(0.0, p - margin), min(1.0, p + margin)


def _choose_start(
    grid_map: GridMap,
    rng: random.Random,
    entry_points: Sequence[tuple[int, int, float]] | None = None,
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
    if not trap_set or grid_map.walkable_count <= 0:
        return CaptureEstimate(0.0, float(time_horizon_steps), 0.0, 0.0)

    rng = random.Random(seed)
    captures = 0
    total_time = 0.0

    for _ in range(max(1, mc_runs)):
        row, col = _choose_start(grid_map, rng, entry_points=entry_points)

        captured = False
        for t in range(1, max(1, time_horizon_steps) + 1):
            if (row, col) in trap_set:
                captures += 1
                total_time += t
                captured = True
                break
            row, col = _step(
                grid_map,
                row,
                col,
                rng,
                movement_model=movement_model,
                bias=bias,
            )
        if not captured:
            total_time += float(time_horizon_steps)

    runs = max(1, mc_runs)
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
    scenarios: list[tuple[str, str, tuple[float, float], int]] = [
        ("lazy_neutral", "lazy", (0.0, 0.0), seed + 11),
        ("biased_right", "biased", (0.5, 0.0), seed + 29),
        ("biased_down", "biased", (0.0, 0.5), seed + 53),
    ]
    scenario_scores: list[dict[str, float]] = []
    score_values: list[float] = []

    for name, model, bias, s in scenarios:
        est = simulate_capture_probability(
            grid_map,
            traps,
            mc_runs=mc_runs,
            time_horizon_steps=time_horizon_steps,
            seed=s,
            movement_model=model,
            bias=bias,
        )
        score_values.append(est.capture_probability)
        scenario_scores.append(
            {
                "name": name,
                "capture_probability": est.capture_probability,
                "expected_time_to_capture": est.expected_time_to_capture,
            }
        )

    robust = min(score_values) if score_values else 0.0
    return RobustCaptureEstimate(robust_score=robust, scenario_scores=scenario_scores)

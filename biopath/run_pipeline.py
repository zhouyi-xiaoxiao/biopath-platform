"""Unified solve pipeline for CLI/API/automation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
from typing import Callable, Iterable, Tuple
from uuid import uuid4

from .candidates import adjacent_to_wall, all_walkable
from .capture import CaptureEstimate, robust_capture_score, simulate_capture_probability
from .mapio import GridMap, load_map_data
from .objective import (
    compute_distance_map,
    distance_metrics,
    mean_distance_to_traps,
    weighted_mean_distance_to_traps,
)
from .optimizer import greedy_optimize
from .report import save_report
from .viz import save_heatmap

Trap = Tuple[int, int]


@dataclass
class SolveOptions:
    k: int = 5
    objective: str = "mean"
    candidate_rule: str = "all_walkable"
    min_wall_neighbors: int = 1
    local_improve: bool = False
    coverage_radius_m: float | None = None
    mc_runs: int = 120
    time_horizon_steps: int = 40
    movement_model: str = "lazy"
    seed: int = 0
    create_run: bool = True


def _sanitize(value: float | None) -> float | str | None:
    if value is None:
        return None
    if math.isinf(value):
        return "inf"
    return float(value)


def _capture_from_primary_scenario(
    scenarios: list[dict[str, float | str]],
    movement_model: str,
) -> CaptureEstimate | None:
    target = f"{str(movement_model).strip().lower()}_neutral"
    fallback = "lazy_neutral"

    for name in (target, fallback):
        for scenario in scenarios:
            if str(scenario.get("name")) != name:
                continue
            return CaptureEstimate(
                capture_probability=float(scenario.get("capture_probability", 0.0)),
                expected_time_to_capture=float(scenario.get("expected_time_to_capture", 0.0)),
                ci95_low=float(scenario.get("ci95_low", 0.0)),
                ci95_high=float(scenario.get("ci95_high", 0.0)),
            )
    return None


def _candidate_cells(
    grid_map: GridMap,
    *,
    candidate_rule: str,
    min_wall_neighbors: int,
) -> list[Trap]:
    if candidate_rule == "all_walkable":
        return all_walkable(grid_map)
    if candidate_rule == "adjacent_to_wall":
        return adjacent_to_wall(grid_map, min_wall_neighbors=min_wall_neighbors)
    raise ValueError("candidate_rule must be 'all_walkable' or 'adjacent_to_wall'")


def _objective_fn(
    grid_map: GridMap,
    objective: str,
    mc_runs: int,
    time_horizon_steps: int,
    seed: int,
    movement_model: str,
) -> Callable[[GridMap, Iterable[Trap]], float]:
    objective_name = objective.lower()
    if objective_name == "mean":
        return mean_distance_to_traps
    if objective_name == "weighted_mean":
        return weighted_mean_distance_to_traps

    cache: dict[tuple[Trap, ...], float] = {}

    def _cached_capture(traps: Iterable[Trap], robust: bool = False) -> float:
        key = tuple(sorted(traps))
        if key in cache:
            return cache[key]
        if robust:
            score = robust_capture_score(
                grid_map,
                key,
                mc_runs=max(40, mc_runs // 2),
                time_horizon_steps=time_horizon_steps,
                seed=seed,
                primary_movement_model=movement_model,
            ).robust_score
        else:
            score = simulate_capture_probability(
                grid_map,
                key,
                mc_runs=max(40, mc_runs // 2),
                time_horizon_steps=time_horizon_steps,
                seed=seed,
                movement_model=movement_model,
            ).capture_probability
        cache[key] = -score
        return cache[key]

    if objective_name == "capture_prob":
        return lambda gm, traps: _cached_capture(traps, robust=False)
    if objective_name == "robust_capture":
        return lambda gm, traps: _cached_capture(traps, robust=True)

    raise ValueError("objective must be one of mean, weighted_mean, capture_prob, robust_capture")


def _score_traps_for_objective(
    grid_map: GridMap,
    traps: Iterable[Trap],
    *,
    objective: str,
    seed: int,
    mc_runs: int,
    time_horizon_steps: int,
    movement_model: str,
) -> float:
    objective_name = objective.lower()
    if objective_name == "mean":
        raw = mean_distance_to_traps(grid_map, traps)
        return -raw if not math.isinf(raw) else -1e9
    if objective_name == "weighted_mean":
        raw = weighted_mean_distance_to_traps(grid_map, traps)
        return -raw if not math.isinf(raw) else -1e9
    if objective_name == "capture_prob":
        return simulate_capture_probability(
            grid_map,
            traps,
            mc_runs=mc_runs,
            time_horizon_steps=time_horizon_steps,
            seed=seed,
            movement_model=movement_model,
        ).capture_probability
    if objective_name == "robust_capture":
        return robust_capture_score(
            grid_map,
            traps,
            mc_runs=mc_runs,
            time_horizon_steps=time_horizon_steps,
            seed=seed,
            primary_movement_model=movement_model,
        ).robust_score
    raise ValueError("objective must be one of mean, weighted_mean, capture_prob, robust_capture")


def evaluate_random_baseline(
    grid_map: GridMap,
    candidates: list[Trap],
    *,
    k: int,
    objective: str,
    samples: int,
    seed: int,
    mc_runs: int,
    time_horizon_steps: int,
    movement_model: str,
) -> dict[str, float]:
    rng = random.Random(seed)
    if not candidates:
        return {"best": 0.0, "mean": 0.0}

    scores: list[float] = []

    for i in range(max(1, samples)):
        traps = rng.sample(candidates, min(k, len(candidates)))
        score = _score_traps_for_objective(
            grid_map,
            traps,
            objective=objective,
            seed=seed + i,
            mc_runs=mc_runs,
            time_horizon_steps=time_horizon_steps,
            movement_model=movement_model,
        )
        scores.append(score)

    return {
        "best": max(scores),
        "mean": sum(scores) / len(scores),
    }


def evaluate_heuristic_baseline(
    grid_map: GridMap,
    candidates: list[Trap],
    *,
    k: int,
    objective: str,
    seed: int,
    mc_runs: int,
    time_horizon_steps: int,
    movement_model: str,
    min_spacing_cells: int = 5,
) -> dict[str, object]:
    """Build a deterministic heuristic baseline with wall + prior weighting.

    This approximates practical rule-based placement (edge preference + hotspot
    preference + spacing) and serves as a stronger baseline than pure random.
    """
    if not candidates:
        return {"mean": 0.0, "best": 0.0, "traps": []}

    def _wall_neighbors(row: int, col: int) -> int:
        count = 0
        for nr, nc in grid_map.neighbors4(row, col):
            if not grid_map.is_walkable(nr, nc):
                count += 1
        return count

    # Weight and edge-following are both useful priors in practical deployment.
    ranked = []
    for row, col in candidates:
        weight = grid_map.weights[row][col]
        wall = _wall_neighbors(row, col)
        edge_bonus = 0.45 if wall >= 1 else 0.0
        strong_edge_bonus = 0.45 if wall >= 2 else 0.0
        score = weight + edge_bonus + strong_edge_bonus
        ranked.append((score, weight, wall, row, col))

    # Stable tie-breaker ensures reproducibility.
    ranked.sort(key=lambda x: (x[0], x[1], x[2], -x[3], -x[4]), reverse=True)

    selected: list[Trap] = []

    def _distance(a: Trap, b: Trap) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    for _, _, _, row, col in ranked:
        if len(selected) >= max(1, k):
            break
        if all(_distance((row, col), existing) >= min_spacing_cells for existing in selected):
            selected.append((row, col))

    # Fallback if strict spacing prevents filling all k traps.
    if len(selected) < max(1, k):
        for _, _, _, row, col in ranked:
            if len(selected) >= max(1, k):
                break
            trap = (row, col)
            if trap in selected:
                continue
            selected.append(trap)

    score = _score_traps_for_objective(
        grid_map,
        selected,
        objective=objective,
        seed=seed + 707,
        mc_runs=mc_runs,
        time_horizon_steps=time_horizon_steps,
        movement_model=movement_model,
    )
    return {
        "best": score,
        "mean": score,
        "traps": [{"row": r, "col": c} for r, c in selected],
    }


def run_solve(
    map_data: dict,
    *,
    runs_root: str | Path,
    options: SolveOptions,
) -> dict:
    grid_map = load_map_data(map_data)
    objective_name = options.objective.lower()
    candidates = _candidate_cells(
        grid_map,
        candidate_rule=options.candidate_rule,
        min_wall_neighbors=options.min_wall_neighbors,
    )
    objective_fn = _objective_fn(
        grid_map,
        objective_name,
        mc_runs=options.mc_runs,
        time_horizon_steps=options.time_horizon_steps,
        seed=options.seed,
        movement_model=options.movement_model,
    )

    traps, objective_raw = greedy_optimize(
        grid_map,
        candidates,
        options.k,
        local_improve=options.local_improve,
        objective_fn=objective_fn,
    )

    distance_map = compute_distance_map(grid_map, traps)
    metrics = distance_metrics(grid_map, distance_map, coverage_radius_m=options.coverage_radius_m)

    robust = robust_capture_score(
        grid_map,
        traps,
        mc_runs=options.mc_runs,
        time_horizon_steps=options.time_horizon_steps,
        seed=options.seed,
        primary_movement_model=options.movement_model,
    )

    capture: CaptureEstimate | None = None
    if objective_name == "robust_capture":
        capture = _capture_from_primary_scenario(
            robust.scenario_scores,
            movement_model=options.movement_model,
        )

    if capture is None:
        capture = simulate_capture_probability(
            grid_map,
            traps,
            mc_runs=options.mc_runs,
            time_horizon_steps=options.time_horizon_steps,
            seed=options.seed,
            movement_model=options.movement_model,
        )

    if objective_name == "mean":
        objective_value = metrics.get("mean_distance_m", float("inf"))
    elif objective_name == "weighted_mean":
        objective_value = metrics.get("weighted_mean_distance_m", float("inf"))
    elif objective_name == "capture_prob":
        objective_value = capture.capture_probability
    else:
        objective_value = robust.robust_score

    now = datetime.now(timezone.utc)
    run_id = now.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    runs_root = Path(runs_root)
    run_dir = runs_root / run_id
    heatmap_path = run_dir / "heatmap.png"
    report_path = run_dir / "summary.md"
    metrics_path = run_dir / "metrics.json"

    if options.create_run:
        run_dir.mkdir(parents=True, exist_ok=True)
        save_heatmap(grid_map, distance_map, traps, heatmap_path)
        save_report(
            grid_map,
            traps,
            objective_value=float(objective_value) if not isinstance(objective_value, str) else 0.0,
            objective_name=objective_name,
            metrics=metrics,
            coverage_radius_m=options.coverage_radius_m,
            out_path=report_path,
            image_path="heatmap.png",
        )

    result = {
        "run_id": run_id,
        "created_at": now.isoformat(),
        "solver_version": "v0.2-auto",
        "map": {
            "name": grid_map.name,
            "cell_size_m": grid_map.cell_size_m,
            "height": grid_map.height,
            "width": grid_map.width,
        },
        "objective": {
            "name": objective_name,
            "raw": _sanitize(objective_raw),
            "value": _sanitize(objective_value if isinstance(objective_value, float) else float(objective_value)),
        },
        "traps": [
            {
                "row": r,
                "col": c,
                "x_m": c * grid_map.cell_size_m,
                "y_m": r * grid_map.cell_size_m,
            }
            for r, c in traps
        ],
        "metrics": {k: _sanitize(v) for k, v in metrics.items()},
        "capture_probability": capture.capture_probability,
        "expected_time_to_capture": capture.expected_time_to_capture,
        "ci95_low": capture.ci95_low,
        "ci95_high": capture.ci95_high,
        "robust_score": robust.robust_score,
        "scenario_scores": robust.scenario_scores,
        "artifacts": {
            "run_dir": str(run_dir),
            "heatmap": str(heatmap_path),
            "summary": str(report_path),
            "metrics": str(metrics_path),
        },
    }

    if options.create_run:
        metrics_path.write_text(json.dumps(result, indent=2))
        latest_path = runs_root / "latest.json"
        latest_path.write_text(json.dumps(result, indent=2))

    return result

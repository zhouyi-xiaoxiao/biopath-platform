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
from .capture import robust_capture_score, simulate_capture_probability
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

    objective_name = objective.lower()
    scores: list[float] = []

    for i in range(max(1, samples)):
        traps = rng.sample(candidates, min(k, len(candidates)))
        if objective_name in ("mean", "weighted_mean"):
            if objective_name == "mean":
                raw = mean_distance_to_traps(grid_map, traps)
            else:
                raw = weighted_mean_distance_to_traps(grid_map, traps)
            score = -raw if not math.isinf(raw) else -1e9
        elif objective_name == "capture_prob":
            score = simulate_capture_probability(
                grid_map,
                traps,
                mc_runs=mc_runs,
                time_horizon_steps=time_horizon_steps,
                seed=seed + i,
                movement_model=movement_model,
            ).capture_probability
        else:
            score = robust_capture_score(
                grid_map,
                traps,
                mc_runs=mc_runs,
                time_horizon_steps=time_horizon_steps,
                seed=seed + i,
            ).robust_score
        scores.append(score)

    return {
        "best": max(scores),
        "mean": sum(scores) / len(scores),
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

    capture = simulate_capture_probability(
        grid_map,
        traps,
        mc_runs=options.mc_runs,
        time_horizon_steps=options.time_horizon_steps,
        seed=options.seed,
        movement_model=options.movement_model,
    )
    robust = robust_capture_score(
        grid_map,
        traps,
        mc_runs=options.mc_runs,
        time_horizon_steps=options.time_horizon_steps,
        seed=options.seed,
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

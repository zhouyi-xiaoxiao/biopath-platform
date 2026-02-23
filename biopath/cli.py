"""Typer CLI for BioPath."""

from __future__ import annotations

import json
import math
from pathlib import Path

import typer

from .candidates import adjacent_to_wall, all_walkable
from .capture import robust_capture_score, simulate_capture_probability
from .mapio import load_map
from .objective import (
    compute_distance_map,
    distance_metrics,
    mean_distance_to_traps,
    weighted_mean_distance_to_traps,
)
from .optimizer import greedy_optimize
from .report import save_report
from .viz import save_heatmap

app = typer.Typer(add_completion=False)


@app.command()
def solve(
    map: Path = typer.Option(..., "--map", exists=True, dir_okay=False, readable=True),
    k: int = typer.Option(..., "--k", min=1),
    out: Path | None = typer.Option(None, "--out"),
    out_json: Path | None = typer.Option(None, "--out-json"),
    report: Path | None = typer.Option(None, "--report"),
    candidate_rule: str = typer.Option("all_walkable", "--candidate-rule"),
    min_wall_neighbors: int = typer.Option(1, "--min-wall-neighbors"),
    local_improve: bool = typer.Option(False, "--local-improve/--no-local-improve"),
    objective: str = typer.Option("mean", "--objective"),
    coverage_radius_m: float | None = typer.Option(None, "--coverage-radius-m"),
    mc_runs: int = typer.Option(120, "--mc-runs", min=20),
    time_horizon_steps: int = typer.Option(40, "--time-horizon-steps", min=5),
    movement_model: str = typer.Option("lazy", "--movement-model"),
    seed: int = typer.Option(7, "--seed"),
) -> None:
    """Solve the trap placement problem for a map."""
    # Keep direct Python invocation compatible with tests that call solve(...) directly.
    if not isinstance(mc_runs, int):
        mc_runs = int(getattr(mc_runs, "default", 120))
    if not isinstance(time_horizon_steps, int):
        time_horizon_steps = int(getattr(time_horizon_steps, "default", 40))
    if not isinstance(seed, int):
        seed = int(getattr(seed, "default", 7))
    if not isinstance(movement_model, str):
        movement_model = str(getattr(movement_model, "default", "lazy"))

    grid_map = load_map(map)

    if candidate_rule == "all_walkable":
        candidates = all_walkable(grid_map)
    elif candidate_rule == "adjacent_to_wall":
        candidates = adjacent_to_wall(grid_map, min_wall_neighbors=min_wall_neighbors)
    else:
        raise typer.BadParameter("candidate-rule must be 'all_walkable' or 'adjacent_to_wall'")

    objective_name = objective.lower()
    if objective_name == "mean":
        objective_fn = mean_distance_to_traps
    elif objective_name == "weighted_mean":
        objective_fn = weighted_mean_distance_to_traps
    elif objective_name == "capture_prob":
        cache: dict[tuple[tuple[int, int], ...], float] = {}

        def objective_fn(gm, traps):
            key = tuple(sorted(traps))
            if key not in cache:
                cache[key] = -simulate_capture_probability(
                    gm,
                    key,
                    mc_runs=max(40, mc_runs // 2),
                    time_horizon_steps=time_horizon_steps,
                    seed=seed,
                    movement_model=movement_model,
                ).capture_probability
            return cache[key]

    elif objective_name == "robust_capture":
        cache: dict[tuple[tuple[int, int], ...], float] = {}

        def objective_fn(gm, traps):
            key = tuple(sorted(traps))
            if key not in cache:
                cache[key] = -robust_capture_score(
                    gm,
                    key,
                    mc_runs=max(40, mc_runs // 2),
                    time_horizon_steps=time_horizon_steps,
                    seed=seed,
                ).robust_score
            return cache[key]

    else:
        raise typer.BadParameter(
            "objective must be 'mean', 'weighted_mean', 'capture_prob', or 'robust_capture'"
        )
    if coverage_radius_m is not None and coverage_radius_m < 0:
        raise typer.BadParameter("coverage-radius-m must be >= 0")

    traps, _ = greedy_optimize(
        grid_map,
        candidates,
        k,
        local_improve=local_improve,
        objective_fn=objective_fn,
    )
    distance_map = compute_distance_map(grid_map, traps)
    metrics = distance_metrics(grid_map, distance_map, coverage_radius_m=coverage_radius_m)
    capture = simulate_capture_probability(
        grid_map,
        traps,
        mc_runs=mc_runs,
        time_horizon_steps=time_horizon_steps,
        seed=seed,
        movement_model=movement_model,
    )
    robust = robust_capture_score(
        grid_map,
        traps,
        mc_runs=mc_runs,
        time_horizon_steps=time_horizon_steps,
        seed=seed,
    )
    if objective_name == "mean":
        objective_value = metrics["mean_distance_m"]
    elif objective_name == "weighted_mean":
        objective_value = metrics["weighted_mean_distance_m"]
    elif objective_name == "capture_prob":
        objective_value = capture.capture_probability
    else:
        objective_value = robust.robust_score

    if out is not None:
        save_heatmap(grid_map, distance_map, traps, out)

    if out_json is not None:
        payload = {
            "map": grid_map.name,
            "cell_size_m": grid_map.cell_size_m,
            "k": len(traps),
            "objective": {"name": objective_name, "value": objective_value},
            "metrics": metrics,
            "capture_probability": capture.capture_probability,
            "expected_time_to_capture": capture.expected_time_to_capture,
            "ci95_low": capture.ci95_low,
            "ci95_high": capture.ci95_high,
            "robust_score": robust.robust_score,
            "scenario_scores": robust.scenario_scores,
            "movement_model": movement_model,
            "mc_runs": mc_runs,
            "time_horizon_steps": time_horizon_steps,
            "seed": seed,
            "weights_provided": grid_map.weights_provided,
            "coverage_radius_m": coverage_radius_m,
            "traps": [
                {
                    "row": r,
                    "col": c,
                    "x_m": c * grid_map.cell_size_m,
                    "y_m": r * grid_map.cell_size_m,
                }
                for r, c in traps
            ],
        }
        out_json.write_text(json.dumps(payload, indent=2))

    if report is not None:
        image_path = str(out) if out is not None else None
        save_report(
            grid_map,
            traps,
            objective_value,
            objective_name=objective_name,
            metrics=metrics,
            coverage_radius_m=coverage_radius_m,
            out_path=report,
            image_path=image_path,
        )

    if isinstance(objective_value, float) and math.isfinite(objective_value):
        typer.echo(f"Objective: {objective_value:.3f}")
    else:
        typer.echo(f"Objective: {objective_value}")


if __name__ == "__main__":
    app()

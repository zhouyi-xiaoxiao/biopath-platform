"""FastAPI endpoints for BioPath website and automation."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import random
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from biopath.mapio import load_map_data
from biopath.run_pipeline import SolveOptions, evaluate_random_baseline, run_solve

ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = ROOT / "runs"

app = FastAPI(title="BioPath API", version="0.2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _extract_map(payload: dict[str, Any]) -> dict:
    map_data = payload.get("map_json")
    if map_data is None:
        map_data = payload.get("map")
    if not isinstance(map_data, dict):
        raise HTTPException(status_code=400, detail="map_json (or map) must be an object")
    return map_data


def _options_from_payload(payload: dict[str, Any]) -> SolveOptions:
    objective = str(payload.get("objective", "capture_prob"))
    return SolveOptions(
        k=int(payload.get("k", 5)),
        objective=objective,
        candidate_rule=str(payload.get("candidate_rule", "all_walkable")),
        min_wall_neighbors=int(payload.get("min_wall_neighbors", 1)),
        local_improve=bool(payload.get("local_improve", True)),
        coverage_radius_m=payload.get("coverage_radius_m"),
        mc_runs=int(payload.get("mc_runs", 120)),
        time_horizon_steps=int(payload.get("time_horizon_steps", 40)),
        movement_model=str(payload.get("movement_model", "lazy")),
        seed=int(payload.get("seed", 7)),
        create_run=bool(payload.get("create_run", True)),
    )


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "BioPath API", "status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.post("/api/solve")
def solve(payload: dict[str, Any]) -> dict[str, Any]:
    map_data = _extract_map(payload)
    options = _options_from_payload(payload)

    try:
        _ = load_map_data(map_data)
        result = run_solve(map_data, runs_root=RUNS_ROOT, options=options)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return result


@app.post("/api/benchmark")
def benchmark(payload: dict[str, Any]) -> dict[str, Any]:
    map_data = _extract_map(payload)
    options = _options_from_payload(payload)
    baseline_samples = int(payload.get("baseline_samples", 40))

    try:
        grid_map = load_map_data(map_data)
        result = run_solve(map_data, runs_root=RUNS_ROOT, options=options)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    from biopath.candidates import adjacent_to_wall, all_walkable

    if options.candidate_rule == "adjacent_to_wall":
        candidates = adjacent_to_wall(grid_map, min_wall_neighbors=options.min_wall_neighbors)
    else:
        candidates = all_walkable(grid_map)

    baseline = evaluate_random_baseline(
        grid_map,
        candidates,
        k=options.k,
        objective=options.objective,
        samples=baseline_samples,
        seed=options.seed + 101,
        mc_runs=options.mc_runs,
        time_horizon_steps=options.time_horizon_steps,
        movement_model=options.movement_model,
    )

    objective_name = options.objective.lower()
    if objective_name in ("mean", "weighted_mean"):
        optimized = -float(result["objective"]["value"])
    elif objective_name == "capture_prob":
        optimized = float(result["capture_probability"])
    else:
        optimized = float(result["robust_score"])

    uplift_vs_mean = optimized - baseline["mean"]
    payload_out = {
        "run": result,
        "baseline": baseline,
        "optimized_score": optimized,
        "uplift_vs_random_mean": uplift_vs_mean,
        "objective": objective_name,
    }

    run_dir = Path(result["artifacts"]["run_dir"])
    (run_dir / "benchmark.json").write_text(json.dumps(payload_out, indent=2))
    return payload_out


@app.get("/api/runs/latest")
def get_latest() -> dict[str, Any]:
    latest = RUNS_ROOT / "latest.json"
    if not latest.exists():
        raise HTTPException(status_code=404, detail="No runs available yet")
    return json.loads(latest.read_text())


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    target = RUNS_ROOT / run_id / "metrics.json"
    if not target.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    return json.loads(target.read_text())


@app.get("/api/runs")
def list_runs(limit: int = 30) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for run_dir in sorted(RUNS_ROOT.glob("*"), reverse=True):
        if not run_dir.is_dir():
            continue
        metrics = run_dir / "metrics.json"
        if not metrics.exists():
            continue
        try:
            row = json.loads(metrics.read_text())
        except Exception:
            continue
        rows.append(
            {
                "run_id": row.get("run_id", run_dir.name),
                "created_at": row.get("created_at"),
                "objective": row.get("objective", {}).get("name"),
                "objective_value": row.get("objective", {}).get("value"),
                "capture_probability": row.get("capture_probability"),
                "robust_score": row.get("robust_score"),
            }
        )
        if len(rows) >= max(1, limit):
            break

    return {"runs": rows}

#!/usr/bin/env python3
"""Run solve + benchmark as a single, reproducible evidence bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from biopath.mapio import load_map_data
from biopath.run_pipeline import SolveOptions, build_benchmark_payload, run_solve


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", default="site/data/cambridge-photo-informed-map.json")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--objective", default="capture_prob")
    parser.add_argument("--mc-runs", type=int, default=120)
    parser.add_argument("--time-horizon-steps", type=int, default=40)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--baseline-samples", type=int, default=40)
    parser.add_argument("--baseline-mode", choices=["heuristic", "random"], default="heuristic")
    parser.add_argument("--heuristic-spacing-cells", type=int, default=5)
    parser.add_argument("--candidate-rule", choices=["all_walkable", "adjacent_to_wall"], default="all_walkable")
    parser.add_argument("--min-wall-neighbors", type=int, default=1)
    parser.add_argument("--runs-root", default="runs")
    args = parser.parse_args()

    map_path = Path(args.map)
    map_data = json.loads(map_path.read_text())
    options = SolveOptions(
        k=args.k,
        objective=args.objective,
        local_improve=True,
        candidate_rule=args.candidate_rule,
        min_wall_neighbors=args.min_wall_neighbors,
        mc_runs=args.mc_runs,
        time_horizon_steps=args.time_horizon_steps,
        seed=args.seed,
        create_run=True,
    )
    result = run_solve(map_data, runs_root=args.runs_root, options=options)

    from biopath.candidates import adjacent_to_wall, all_walkable

    grid_map = load_map_data(map_data)
    if options.candidate_rule == "adjacent_to_wall":
        candidates = adjacent_to_wall(grid_map, min_wall_neighbors=options.min_wall_neighbors)
    else:
        candidates = all_walkable(grid_map)

    benchmark = build_benchmark_payload(
        result=result,
        grid_map=grid_map,
        candidates=candidates,
        options=options,
        baseline_samples=max(1, args.baseline_samples),
        baseline_mode=args.baseline_mode,
        heuristic_spacing_cells=max(1, args.heuristic_spacing_cells),
    )

    print(
        json.dumps(
            {
                "run_id": result["run_id"],
                "objective": result["objective"],
                "capture_probability": result["capture_probability"],
                "robust_score": result["robust_score"],
                "baseline_mode": benchmark["baseline_mode"],
                "baseline_mean": benchmark["baseline"]["mean"],
                "optimized_score": benchmark["optimized_score"],
                "uplift_vs_baseline_pct": benchmark["uplift_vs_baseline_pct"],
                "artifacts": result["artifacts"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

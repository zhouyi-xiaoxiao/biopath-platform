#!/usr/bin/env python3
"""Run a benchmark solve and write latest artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from biopath.run_pipeline import SolveOptions, run_solve


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", default="tests/fixtures/warehouse.json")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--objective", default="capture_prob")
    parser.add_argument("--mc-runs", type=int, default=120)
    parser.add_argument("--time-horizon-steps", type=int, default=40)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--runs-root", default="runs")
    args = parser.parse_args()

    map_path = Path(args.map)
    map_data = json.loads(map_path.read_text())
    options = SolveOptions(
        k=args.k,
        objective=args.objective,
        local_improve=True,
        candidate_rule="all_walkable",
        mc_runs=args.mc_runs,
        time_horizon_steps=args.time_horizon_steps,
        seed=args.seed,
        create_run=True,
    )
    result = run_solve(map_data, runs_root=args.runs_root, options=options)
    print(json.dumps({
        "run_id": result["run_id"],
        "objective": result["objective"],
        "capture_probability": result["capture_probability"],
        "robust_score": result["robust_score"],
        "artifacts": result["artifacts"],
    }, indent=2))


if __name__ == "__main__":
    main()

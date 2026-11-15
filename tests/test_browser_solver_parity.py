"""The public page's browser solver must place the same traps as the package.

site/solver.js is a port of the deterministic path (BFS distance, greedy with
swap improvement, rule-of-thumb baseline). This runs it under Node and compares
it with the Python code on the shipped maps. Skipped quietly if Node is absent.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import shutil
import subprocess

from biopath.candidates import all_walkable
from biopath.mapio import load_map
from biopath.objective import (
    compute_distance_map,
    distance_metrics,
    mean_distance_to_traps,
    weighted_mean_distance_to_traps,
)
from biopath.optimizer import greedy_optimize
from biopath.run_pipeline import evaluate_heuristic_baseline

ROOT = Path(__file__).resolve().parents[1]
# (map, budgets): the pure-Python solver is slow, so the large maps use a few budgets.
CASES = [
    (ROOT / "maps" / "cambridgeshire_demo_farm.json", [1, 3, 6]),
    (ROOT / "maps" / "cambridgeshire_photo_informed.json", [1, 3, 6]),
    (ROOT / "tests" / "fixtures" / "warehouse.json", list(range(1, 9))),
]

NODE_SCRIPT = r"""
const fs = require("fs");
const vm = require("vm");
const ctx = {};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), ctx);
const S = ctx.BioPathSolver;
const out = [];
for (const [path, budgets] of JSON.parse(process.argv[2])) {
  const map = S.parseMap(JSON.parse(fs.readFileSync(path, "utf8")));
  const cands = S.walkables(map);
  const fn = map.weightsProvided ? S.weightedMeanDistance : S.meanDistance;
  for (const k of budgets) {
    const ref = S.greedyOptimize(map, cands, k, true, fn);
    const solved = S.greedyOptimizeFast(map, cands, k, true, map.weightsProvided);
    const base = S.heuristicBaseline(map, cands, k, 5);
    const m = S.distanceMetrics(map, S.distanceMap(map, solved.traps));
    out.push({ path, k, ref, solved, baseline: base, metrics: m });
  }
}
process.stdout.write(JSON.stringify(out));
"""


def _run_node() -> list[dict] | None:
    node = shutil.which("node")
    if node is None:
        print("node not found; browser solver parity check skipped")
        return None
    proc = subprocess.run(
        [
            node,
            "-e",
            NODE_SCRIPT,
            str(ROOT / "site" / "solver.js"),
            json.dumps([[str(p), budgets] for p, budgets in CASES]),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=300,
    )
    return json.loads(proc.stdout)


def test_browser_solver_matches_python() -> None:
    rows = _run_node()
    if rows is None:
        return
    assert len(rows) == sum(len(budgets) for _, budgets in CASES)
    for row in rows:
        grid_map = load_map(row["path"])
        fn = weighted_mean_distance_to_traps if grid_map.weights_provided else mean_distance_to_traps
        traps, objective = greedy_optimize(
            grid_map, all_walkable(grid_map), row["k"], local_improve=True, objective_fn=fn
        )
        label = f"{Path(row['path']).name} k={row['k']}"
        for variant in ("ref", "solved"):
            assert [list(t) for t in traps] == row[variant]["traps"], f"{label} {variant}"
            assert math.isclose(objective, row[variant]["objective"], rel_tol=0, abs_tol=1e-12), f"{label} {variant}"

        metrics = distance_metrics(grid_map, compute_distance_map(grid_map, traps))
        for name in ("mean_distance_m", "weighted_mean_distance_m", "max_distance_m", "p95_distance_m"):
            assert math.isclose(metrics[name], row["metrics"][name], abs_tol=1e-12), f"{label} {name}"

        baseline = evaluate_heuristic_baseline(
            grid_map,
            all_walkable(grid_map),
            k=row["k"],
            objective="mean",
            seed=7,
            mc_runs=40,
            time_horizon_steps=40,
            movement_model="lazy",
        )
        assert [[t["row"], t["col"]] for t in baseline["traps"]] == row["baseline"], f"{label} baseline"

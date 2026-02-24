# BioPath Spec (Current MVP)

## Product Contract

BioPath takes a grid-style site map and fixed trap budget `k`, then returns:

1. Trap coordinates.
2. Scenario-aware capture metrics.
3. A reproducible artifact bundle (`metrics.json`, `summary.md`, `heatmap.png`, optional `benchmark.json`).

The public demo relies on one fixed proof contract:

- Optimized score (under selected objective)
- Baseline mean (primary: heuristic, secondary: random)
- Uplift vs baseline
- Robust score (worst-case across stress scenarios)
- Monte Carlo run count

## Inputs

Map JSON:

- `name`: string
- `cell_size_m`: number
- `ascii`: list of strings (`#` = obstacle, `.` = walkable)
- optional `weights`: non-negative matrix (same shape as `ascii`)

Solve options:

- `k`
- `objective`: `mean | weighted_mean | capture_prob | robust_capture`
- `candidate_rule`: `all_walkable | adjacent_to_wall`
- `min_wall_neighbors`
- `local_improve`
- `mc_runs`
- `time_horizon_steps`
- `movement_model`: `lazy | unbiased | biased`
- `seed`

## Candidate Generation

- `all_walkable`: every walkable cell is eligible.
- `adjacent_to_wall`: walkable cells with at least `min_wall_neighbors` wall neighbors in 4-neighborhood.

## Optimization Objectives

- `mean`: minimize mean shortest-path distance to nearest trap.
- `weighted_mean`: minimize weighted mean shortest-path distance.
- `capture_prob`: maximize Monte Carlo capture probability.
- `robust_capture`: maximize worst-case scenario capture probability.

Internally, capture-based objectives are solved through greedy selection with objective caching.

## Capture and Robust Metrics

`capture_probability` is estimated by Monte Carlo random-walk simulation:

- random start point from walkable cells (or entry points)
- movement model (`lazy`, `unbiased`, `biased`)
- finite horizon (`time_horizon_steps`)
- confidence interval via normal approximation

`robust_score` is scenario-based:

- evaluate multiple stress scenarios (for example neutral + directional bias + sparse stress)
- `robust_score = min(scenario capture probabilities)`

## Baselines

Benchmarking supports two baselines under the same budget `k`:

- `heuristic` (primary): edge + spacing + prior weighting rules
- `random` (secondary): random trap placements over candidate cells

Uplift fields:

- `uplift_vs_baseline_mean`
- `uplift_vs_baseline_pct`
- `uplift_vs_random_mean`
- `uplift_vs_random_pct`

## Outputs

From `/api/solve`:

- run metadata (`run_id`, `created_at`, map info)
- objective value
- trap coordinates
- distance metrics
- capture metrics (`capture_probability`, `ci95_low/high`, `expected_time_to_capture`)
- robust metrics (`robust_score`, `scenario_scores`)
- artifact paths (`run_dir`, `summary`, `heatmap`, `metrics`)

From `/api/benchmark`:

- all solve outputs above
- baseline details (`baseline`, `baselines`, `baseline_mode`)
- uplift metrics
- benchmark artifact persisted to `runs/<run_id>/benchmark.json`

## Site Publishing Contract

`bash scripts/publish_site.sh` must publish a single-source evidence bundle to `site/data/`:

- `latest.json`
- `latest-summary.md`
- `latest-heatmap.png`
- `latest-benchmark.json` (if present for the same run)
- `runs.json`

This prevents mixed-run data in Pitch Safe mode.

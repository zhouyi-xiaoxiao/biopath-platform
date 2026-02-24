# Metrics and Proof Contract

This document defines the metrics shown in API responses, reports, and Pitch Safe mode.

## Core Metrics

- `capture_probability`: fraction of Monte Carlo simulations that hit any trap within horizon.
- `robust_score`: conservative score = minimum capture probability across stress scenarios.
- `expected_time_to_capture`: average step count until capture (capped by horizon when uncaptured).
- `ci95_low`, `ci95_high`: normal-approximation 95% CI for capture probability.

Distance metrics are still reported for spatial diagnostics:

- `mean_distance_m`
- `weighted_mean_distance_m`
- `max_distance_m`
- `p95_distance_m`

## Scenario-Robust Definition

Given scenario set `S` and per-scenario capture probability `p_s`:

- `robust_score = min_{s in S} p_s`

This is scenario stress testing with worst-case readout.

## Baselines

Benchmark mode compares optimized score against two baselines under the same `k`:

- Primary: `heuristic` baseline (edge + spacing + prior)
- Secondary: `random` baseline

Reported uplift:

- `uplift_vs_baseline_mean = optimized_score - baseline.mean`
- `uplift_vs_baseline_pct = uplift_vs_baseline_mean / baseline.mean`
- `uplift_vs_random_mean`
- `uplift_vs_random_pct`

## Proof Contract (What to Read on Stage)

For one fixed run:

1. Optimized score
2. Baseline mean (heuristic primary)
3. Uplift vs baseline
4. Robust score
5. Monte Carlo run count

If these five fields come from the same `run_id`, the claim is complete and auditable.

## Output Surfaces

- `runs/<run_id>/metrics.json`: full solve output
- `runs/<run_id>/benchmark.json`: baseline + uplift
- `runs/<run_id>/summary.md`: human-readable report including proof block
- `site/data/latest*.json|md|png`: published Pitch Safe evidence bundle

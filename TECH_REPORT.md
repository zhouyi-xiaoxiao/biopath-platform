# BioPath MVP Technical Report

## 1. System Overview

BioPath is a decision-support platform for trap placement under uncertainty.
It converts a structured site map into trap coordinates, uncertainty-aware performance metrics,
and rerunnable artifacts for audit and benchmarking.

Core principle: optimize under a fixed trap budget and prove value against explicit baselines.

## 2. Architecture

- Map parsing and validation: `biopath/mapio.py`
- Candidate generation: `biopath/candidates.py`
- Distance metrics: `biopath/objective.py`
- Capture + robust scoring: `biopath/capture.py`
- Greedy solver pipeline and run artifacts: `biopath/run_pipeline.py`
- Report and heatmap output: `biopath/report.py`, `biopath/viz.py`
- API endpoints: `api/main.py`
- Demo website and pitch UI: `site/`
- Automation/publishing scripts: `scripts/`

## 3. Data Model

A `GridMap` includes:

- `ascii` walkability grid
- `cell_size_m`
- optional `weights` (risk/activity prior)

Derived fields include dimensions, walkable count, and aggregate weights.

## 4. Optimization and Scoring

### 4.1 Candidate Sets

- `all_walkable`: full feasible set
- `adjacent_to_wall`: edge-favoring subset

### 4.2 Objectives

- `mean`: minimize unweighted nearest-trap shortest-path distance
- `weighted_mean`: minimize weighted nearest-trap shortest-path distance
- `capture_prob`: maximize Monte Carlo-estimated capture probability
- `robust_capture`: maximize conservative (worst-case) scenario score

Capture-based objectives are optimized with greedy trap selection and cached candidate evaluation.

### 4.3 Monte Carlo Capture Estimation

For each run:

1. Sample start position.
2. Simulate movement by model (`lazy`, `unbiased`, `biased`).
3. Stop on trap hit or horizon expiry.
4. Aggregate capture probability and expected time to capture.
5. Compute 95% CI from Bernoulli approximation.

### 4.4 Scenario-Robust Score

`robust_capture_score` evaluates multiple stress scenarios (neutral + directional/sparse stress)
and returns:

- per-scenario capture metrics
- `robust_score = min(scenario capture probabilities)`

This is scenario-robust evaluation (worst-case over predefined stress scenarios), not a full
uncertainty-set RO formulation.

## 5. Baseline and Uplift Framework

`/api/benchmark` and `scripts/run_benchmark.py` evaluate optimized output against:

- primary baseline: heuristic (edge + spacing + prior)
- secondary baseline: random placements

Reported uplift metrics:

- absolute and relative uplift vs selected baseline
- absolute and relative uplift vs random baseline

Benchmark output is persisted to `runs/<run_id>/benchmark.json`.

## 6. Artifact Contract and Reproducibility

Each solve run writes:

- `runs/<run_id>/metrics.json`
- `runs/<run_id>/summary.md`
- `runs/<run_id>/heatmap.png`

Benchmark runs additionally write:

- `runs/<run_id>/benchmark.json`

`summary.md` now includes a proof contract block:

- capture probability
- robust score
- capture CI
- MC run count
- seed and movement model
- scenario scores

## 7. Website Publishing Model

`scripts/publish_site.sh` publishes a coherent site bundle:

- `site/data/latest.json`
- `site/data/latest-summary.md`
- `site/data/latest-heatmap.png`
- `site/data/latest-benchmark.json` (same run when available)
- `site/data/runs.json`

The script avoids stale benchmark carry-over if no benchmark exists for the latest run.

## 8. API Endpoints

- `POST /api/solve`: compute optimized traps and solve metrics
- `POST /api/benchmark`: solve + baselines + uplift + benchmark artifact
- `GET /api/runs/latest`: latest run payload
- `GET /api/runs/{run_id}`: run metrics by id
- `GET /api/runs`: recent runs summary

## 9. Limitations

- Greedy optimization is fast and practical but not globally optimal.
- Movement dynamics are demonstration-grade proxies, not biologically calibrated models.
- Scenario set is predefined and should be calibrated with pilot telemetry.

## 10. Next Technical Milestones

- Add calibrated entry-point priors from pilot observations.
- Introduce confidence-aware decision thresholds (for low-CI runs).
- Add run-to-run regression checks for proof contract stability.
- Expand export templates for compliance workflows.

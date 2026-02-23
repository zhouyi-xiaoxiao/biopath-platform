# BioPath Pitch Quickstart

This guide is for first-time demo operators.

## Goal

Finish one complete demo in 2 minutes:

1. Connect API.
2. Run solve.
3. Run benchmark.
4. Read proof metrics.
5. Switch to pitch mode.

## Before you start

1. Start API: `uvicorn api.main:app --host 0.0.0.0 --port 8001`
2. Serve site: `python -m http.server 8080 --directory site`
3. Open UI: `http://127.0.0.1:8080/?api=http://127.0.0.1:8001`

## 30-second startup checklist

1. Click `Auto Connect`.
2. Confirm connection badge turns `Connected`.
3. Keep default Cambridge demo map.
4. Keep default objective `robust_capture` and `k=6`.

## 2-minute live demo checklist

1. Click `Run Solve`.
2. Click `Run Benchmark`.
3. Read these values out loud from Proof Panel:
   - `capture_probability`
   - `robust_score`
   - `uplift_vs_random_mean`
4. Click `Open Pitch Mode`.
5. Use copy buttons in Narrative Panel.

## Failure recovery playbook

1. API unreachable:
   - Use top red banner button `Fix in 1 step`.
   - Run `Health Check`.
2. Map JSON invalid:
   - Read line/column hint below the map box.
   - Fix only that line and retry.
3. Benchmark timeout:
   - Click `Retry with lower MC`.
4. Empty run history:
   - Click `Run first benchmark now`.

## 60-second speaking script

Problem: Manual trap placement is inconsistent and misses bottlenecks in complex farm layouts.

Solution: BioPath turns a simple map into optimized trap coordinates and a reproducible plan.

Proof: We benchmark against random baseline with Monte Carlo validation and robust capture metrics.

Ask: We ask for 2 pilot introductions, a small PoC budget, and practical data access for an 8-week farm trial.

## Query shortcuts

- `?api=<url>` preset API base
- `?tour=1` force guided tour
- `?pitch=1` open in pitch mode

## Stable local storage keys

- `biopath_api_base`
- `biopath_tour_completed`
- `biopath_ui_mode`

# BioPath Pitch Quickstart

Use this when you need a stable stage demo in 2 minutes.

## Goal

Complete one clear flow:

1. Connect API (or use Pitch Safe fallback).
2. Run solve.
3. Run benchmark.
4. Read proof contract.
5. Deliver ask.

## Fast start (recommended)

1. In the project root, run:
   - `bash scripts/start_public_demo.sh`
2. Open the generated pitch URL.
3. Click `Auto Connect` in Studio.

If live API fails, continue in `Pitch Safe` mode (curated proof is still presentation-ready).

## Local-only mode

1. Start API: `python3 -m uvicorn api.main:app --host 127.0.0.1 --port 8001`
2. Serve site: `python3 -m http.server 8080 --directory site`
3. Open: `http://127.0.0.1:8080/?api=http://127.0.0.1:8001&tour=1`

## 2-minute demo checklist

1. Click `Run Solve`.
2. Click `Run Benchmark`.
3. Read these values from Proof Panel:
   - Optimized capture probability
   - Heuristic baseline mean
   - Uplift vs heuristic baseline
   - Robust score (conservative under uncertainty)
   - MC runs
4. Switch to pitch narrative and deliver Ask.

## If something breaks

1. API unreachable:
   - stay in Pitch Safe and continue script
   - or rerun `bash scripts/start_public_demo.sh`
2. Map JSON invalid:
   - use line/column hint under map box
3. Benchmark timeout:
   - lower `MC Runs` and retry
4. Empty run list:
   - use curated proof and one-page guide

## 60-second backup speech

Problem: Manual placement is inconsistent, hard to audit, and misses chokepoints.

Solution: BioPath turns one map into optimized trap coordinates plus a reproducible run artifact.

Proof: With fixed k, BioPath benchmarks against a heuristic baseline and reports uplift, robust capture, and Monte Carlo validation.

Ask: Two pilot introductions, one 8-week trial site, and support for a £5k–£20k LINCAM PoC application.

## URL shortcuts

- `?api=<url>` preset API base
- `?tour=1` force guided tour
- `?pitch=1` open pitch-safe mode

## Local storage keys

- `biopath_api_base`
- `biopath_tour_completed`
- `biopath_ui_mode` (`ops|pitch_safe|pitch_live`)

# BioPath Platform

BioPath is a trap-placement optimization platform for farm and facility layouts.

It now includes:

- CLI solver (`mean`, `weighted_mean`, `capture_prob`, `robust_capture`)
- FastAPI backend (`/api/solve`, `/api/benchmark`, `/api/runs/latest`, `/api/runs/{run_id}`)
- Static website (`site/`) for live demo, compare, and iteration history
- Automation scripts for repeatable runs and escalation workflows
- A Cambridge-region inspired demo map (`maps/cambridgeshire_demo_farm.json`)

## Quickstart

```bash
python -m pip install -e '.[dev]'
python -m biopath.cli solve --map tests/fixtures/warehouse.json --k 5 --objective capture_prob --mc-runs 120 --time-horizon-steps 40 --out out.png --out-json out.json --report report.md
```

## Run API

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8001
```

Example request:

```bash
curl -X POST http://127.0.0.1:8001/api/solve \
  -H 'Content-Type: application/json' \
  -d '{"map_path":"maps/cambridgeshire_demo_farm.json","k":6,"objective":"robust_capture","mc_runs":160,"time_horizon_steps":48}'
```

## Run Website

Serve static `site/` and configure `API Base URL` in UI:

```bash
python -m http.server 8080 --directory site
```

Then open `http://127.0.0.1:8080`.

Useful query shortcuts:

- `?api=<url>` prefill and auto-probe API base
- `?tour=1` force open guided 6-step tour
- `?pitch=1` launch directly in pitch mode

Pitch helper pages:

- One-page printable guide: `site/quickstart-onepager.html`
- Detailed checklist: `docs/PITCH_QUICKSTART.md`

## Public Demo Link (No Render Account Needed)

If your Render API is not ready, you can still get a public API URL immediately:

```bash
bash scripts/start_public_demo.sh
```

This starts local API on `127.0.0.1:8001`, creates a public HTTPS tunnel, and prints:

- `API URL`
- `Pitch URL` (GitHub Pages URL prefilled with `?api=...&tour=1`)

Stop it with:

```bash
bash scripts/stop_public_demo.sh
```

## Automation scripts

```bash
# benchmark + publish site fallback data + tests
bash scripts/auto_iterate.sh

# one benchmark run
python scripts/run_benchmark.py --map maps/cambridgeshire_demo_farm.json --k 6 --objective robust_capture

# publish latest run into site/data/
bash scripts/publish_site.sh
```

## Escalation workflow (GPT-5.2 Pro web)

```bash
# put a hard problem in escalations/pending/<id>.md
python scripts/escalate_to_gpt52_web.py --question escalations/pending/example.md --answer escalations/answers/example.md
bash scripts/escalation_worker.sh
```

Worker behavior:

- retries web escalation up to 3 attempts
- then runs Codex CLI with `gpt-5.3-codex` and `xhigh` reasoning
- runs tests and appends output to `escalations/actions/<id>.md`

## Map format

A map JSON must include:

- `name`: string
- `cell_size_m`: float, meters per cell
- `ascii`: list of strings with `#` for obstacles and `.` for walkable cells

Optional fields:

- `weights`: list of lists (same shape as `ascii`) with non-negative numbers for walkable cells.
  Obstacles should be `0` or `null`. When omitted, every walkable cell has weight 1.0.

Example:

```json
{
  "name": "Simple room",
  "cell_size_m": 1.0,
  "ascii": [
    "#####",
    "#...#",
    "#...#",
    "#####"
  ]
}
```

Weighted example:

```json
{
  "name": "Weighted room",
  "cell_size_m": 1.0,
  "ascii": [
    "#####",
    "#...#",
    "#...#",
    "#...#",
    "#####"
  ],
  "weights": [
    [0, 0, 0, 0, 0],
    [0, 1, 1, 1, 0],
    [0, 1, 5, 1, 0],
    [0, 1, 1, 1, 0],
    [0, 0, 0, 0, 0]
  ]
}
```

## CLI

```bash
python -m biopath.cli solve --map <path> --k <int> --out <png> --out-json <json> --report <md>
```

Optional flags:

- `--candidate-rule` (`all_walkable` or `adjacent_to_wall`)
- `--min-wall-neighbors` (only used for `adjacent_to_wall`)
- `--local-improve/--no-local-improve`
- `--objective` (`mean`, `weighted_mean`, `capture_prob`, `robust_capture`)
- `--coverage-radius-m` (report coverage within a distance threshold)
- `--mc-runs` (Monte Carlo run count)
- `--time-horizon-steps` (capture horizon)
- `--movement-model` (`lazy`, `unbiased`, `biased`)
- `--seed`

## Testing

```bash
python3 -P -m pytest -q tests
```

UI smoke test (Playwright):

```bash
npm install
npx playwright install chromium
npm run test:ui
```

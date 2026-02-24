# BioPath Platform

BioPath turns a site map into trap coordinates plus a rerunnable proof bundle.

`Map in -> traps out -> proof attached.`

## What the proof bundle contains

For one fixed run (`run_id`):

- optimized score
- heuristic baseline mean (primary) + random baseline (secondary)
- uplift vs baseline
- robust score (worst-case across stress scenarios)
- Monte Carlo run count

## 2-minute reproducible flow

```bash
python -m pip install -e '.[dev]'

python3 scripts/run_benchmark.py \
  --map site/data/cambridge-photo-informed-map.json \
  --k 6 \
  --objective capture_prob \
  --mc-runs 140 \
  --time-horizon-steps 48 \
  --seed 7 \
  --baseline-mode heuristic \
  --baseline-samples 40

bash scripts/publish_site.sh
python3 scripts/sync_pitch_from_latest.py
```

Then serve the site:

```bash
python -m http.server 8080 --directory site
```

Open `http://127.0.0.1:8080`.

## API

Run API:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8001
```

Endpoints:

- `POST /api/solve`
- `POST /api/benchmark`
- `GET /api/runs/latest`
- `GET /api/runs/{run_id}`
- `GET /api/runs`

Example:

```bash
curl -X POST http://127.0.0.1:8001/api/benchmark \
  -H 'Content-Type: application/json' \
  -d '{
    "map_path": "site/data/cambridge-photo-informed-map.json",
    "k": 6,
    "objective": "capture_prob",
    "mc_runs": 140,
    "time_horizon_steps": 48,
    "seed": 7,
    "baseline_mode": "heuristic",
    "baseline_samples": 40
  }'
```

## Documentation

- Metrics and proof definitions: `docs/METRICS_AND_PROOF.md`
- Reproducibility workflow: `docs/REPRODUCIBILITY.md`
- Commercial ROI model: `docs/COMMERCIAL_ROI_MODEL.md`
- OpenClaw/Codex multi-agent workflow: `docs/MULTIAGENT_PLAYBOOK.md`
- Pitch quickstart: `docs/PITCH_QUICKSTART.md`
- Judge Q&A bank: `docs/PITCH_QA_BANK.md`

## CLI

```bash
python -m biopath.cli solve --map <path> --k <int> --objective capture_prob --mc-runs 120 --time-horizon-steps 40 --out-json out.json --report report.md
```

## Tests

```bash
python3 -P -m pytest -q tests
```

UI smoke (Playwright):

```bash
npm install
npx playwright install chromium
npm run test:ui
```

## Developer utilities (optional)

Automation and escalation scripts under `scripts/` speed up iteration, but they are not runtime dependencies of the solver/API/product proof flow.

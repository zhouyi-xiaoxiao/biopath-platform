# Reproducibility Guide

## Goal

Generate one coherent evidence bundle where all published artifacts reference the same run.

## Standard Command

```bash
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

## Generated Files

Run directory (`runs/<run_id>/`):

- `metrics.json`
- `summary.md`
- `heatmap.png`
- `benchmark.json`

Published site bundle (`site/data/`):

- `latest.json`
- `latest-summary.md`
- `latest-heatmap.png`
- `latest-benchmark.json`
- `runs.json`

Pitch assets synced from latest bundle:

- `site/pitch-deck.html`
- `site/pitch-script.html`
- `site/assets/cambridge-photo-informed-summary.md`
- `site/assets/cambridge-photo-informed-solve.json`

## Consistency Check

Verify `run_id` matches:

```bash
python3 - <<'PY'
import json
from pathlib import Path
root = Path('.')
latest = json.loads((root / 'site/data/latest.json').read_text())
bench = json.loads((root / 'site/data/latest-benchmark.json').read_text())
print('latest run_id   :', latest.get('run_id'))
print('benchmark run_id:', bench.get('run_id'))
print('MATCH:', latest.get('run_id') == bench.get('run_id'))
PY
```

## Notes

- If a latest run has no `benchmark.json`, `publish_site.sh` removes stale `latest-benchmark.json` to avoid mixed-run proof.
- Use fixed seeds for presentation-grade reproducibility.
- Use larger `mc_runs` for higher-confidence claims at the cost of runtime.

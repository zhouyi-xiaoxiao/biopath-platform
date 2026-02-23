#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/site/data"

if [[ -f "$ROOT/runs/latest.json" ]]; then
  cp "$ROOT/runs/latest.json" "$ROOT/site/data/latest.json"
fi

python3 - "$ROOT" <<'PY'
import json
import sys
from pathlib import Path
root = Path(sys.argv[1])
rows = []
for p in sorted(root.glob("runs/*/metrics.json"), reverse=True):
    try:
        d = json.loads(p.read_text())
    except Exception:
        continue
    rows.append({
        "run_id": d.get("run_id"),
        "created_at": d.get("created_at"),
        "capture_probability": d.get("capture_probability"),
        "robust_score": d.get("robust_score"),
        "objective": d.get("objective", {}).get("name"),
    })
    if len(rows) >= 120:
        break
(root / "site" / "data" / "runs.json").write_text(json.dumps({"runs": rows}, indent=2))
PY

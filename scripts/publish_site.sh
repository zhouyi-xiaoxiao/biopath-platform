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
import shutil
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

latest = root / "runs" / "latest.json"
if latest.exists():
    try:
        latest_data = json.loads(latest.read_text())
    except Exception:
        latest_data = {}
    heatmap = latest_data.get("artifacts", {}).get("heatmap")
    summary = latest_data.get("artifacts", {}).get("summary")
    if heatmap:
        hp = Path(str(heatmap))
        if not hp.is_absolute():
            hp = (root / hp).resolve()
        if hp.exists():
            target = root / "site" / "data" / "latest-heatmap.png"
            shutil.copyfile(hp, target)
    if summary:
        sp = Path(str(summary))
        if not sp.is_absolute():
            sp = (root / sp).resolve()
        if sp.exists():
            target = root / "site" / "data" / "latest-summary.md"
            shutil.copyfile(sp, target)

site_latest = root / "site" / "data" / "latest.json"
if site_latest.exists():
    try:
        latest_site_data = json.loads(site_latest.read_text())
    except Exception:
        latest_site_data = {}
    latest_site_data["artifacts_site"] = {
        "heatmap": "./data/latest-heatmap.png",
        "summary": "./data/latest-summary.md" if (root / "site" / "data" / "latest-summary.md").exists() else "./assets/cambridge-photo-informed-summary.md",
    }
    site_latest.write_text(json.dumps(latest_site_data, indent=2) + "\n")
PY

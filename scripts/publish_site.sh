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


def resolve_artifact(path_value: str) -> Path:
    candidate = Path(path_value)
    if candidate.is_absolute():
        return candidate
    return (root / candidate).resolve()


latest = root / "runs" / "latest.json"
if latest.exists():
    try:
        latest_data = json.loads(latest.read_text())
    except Exception:
        latest_data = {}

    latest_run_id = str(latest_data.get("run_id", "")).strip()
    heatmap = latest_data.get("artifacts", {}).get("heatmap")
    summary = latest_data.get("artifacts", {}).get("summary")
    run_dir = latest_data.get("artifacts", {}).get("run_dir")

    if heatmap:
        hp = resolve_artifact(str(heatmap))
        if hp.exists():
            target = root / "site" / "data" / "latest-heatmap.png"
            shutil.copyfile(hp, target)

    if summary:
        sp = resolve_artifact(str(summary))
        if sp.exists():
            target = root / "site" / "data" / "latest-summary.md"
            shutil.copyfile(sp, target)

    benchmark_target = root / "site" / "data" / "latest-benchmark.json"
    benchmark_source = None
    if isinstance(run_dir, str) and run_dir.strip():
        candidate = resolve_artifact(run_dir.strip()) / "benchmark.json"
        if candidate.exists():
            benchmark_source = candidate

    if benchmark_source is not None:
        try:
            benchmark_data = json.loads(benchmark_source.read_text())
        except Exception:
            benchmark_data = {}
        benchmark_run_id = str(
            benchmark_data.get("run_id")
            or benchmark_data.get("run", {}).get("run_id")
            or ""
        ).strip()
        if latest_run_id:
            if not benchmark_run_id:
                benchmark_data["run_id"] = latest_run_id
            elif benchmark_run_id != latest_run_id:
                benchmark_data["run_id"] = latest_run_id
        benchmark_target.write_text(json.dumps(benchmark_data, indent=2) + "\n")
    elif benchmark_target.exists():
        benchmark_target.unlink()

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

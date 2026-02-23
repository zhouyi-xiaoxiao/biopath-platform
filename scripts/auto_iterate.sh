#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"

python3 scripts/run_benchmark.py --map maps/cambridgeshire_demo_farm.json --k 6 --objective robust_capture --mc-runs 160 --time-horizon-steps 48 --seed 7
python3 scripts/summarize_delta.py || true
bash scripts/publish_site.sh
python3 -m pytest -q

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
if [[ -n "$(git status --porcelain runs site/data 2>/dev/null)" ]]; then
  branch="codex/auto-$(date -u +%Y%m%d-%H%M%S)"
  git checkout -b "$branch" >/dev/null 2>&1 || git checkout "$branch"
  git add runs site/data
  git commit -m "auto: benchmark iteration update" || true

  if git remote get-url origin >/dev/null 2>&1; then
    git push -u origin "$branch" || true
    if command -v gh >/dev/null 2>&1; then
      gh pr create --fill --base main --head "$branch" || true
    fi
  fi
fi

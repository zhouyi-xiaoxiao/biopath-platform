#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mkdir -p escalations/pending escalations/answers escalations/actions

shopt -s nullglob
for q in escalations/pending/*.md; do
  id="$(basename "$q" .md)"
  a="escalations/answers/${id}.md"
  action="escalations/actions/${id}.md"

  if python3 scripts/escalate_to_gpt52_web.py --question "$q" --answer "$a"; then
    codex exec \
      --dangerously-bypass-approvals-and-sandbox \
      -m gpt-5.3-codex \
      -c model_reasoning_effort='"xhigh"' \
      -C "$ROOT" \
      "Read ${a}. Implement concrete code changes in this repo to address the escalation. Run tests. Write a concise execution report to ${action}." || true

    python3 -m pytest -q >> "$action" 2>&1 || true
    mv "$q" "${q}.done"
  else
    echo "Escalation failed for ${id}; leaving pending file." >&2
  fi
done

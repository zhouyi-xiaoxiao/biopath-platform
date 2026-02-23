#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"

mkdir -p escalations/pending escalations/answers escalations/actions

shopt -s nullglob
for q in escalations/pending/*.md; do
  base="$(basename "$q")"
  if [[ "$base" == TEMPLATE.md || "$base" == *_TEMPLATE.md ]]; then
    continue
  fi
  id="$(basename "$q" .md)"
  a="escalations/answers/${id}.md"
  action="escalations/actions/${id}.md"

  attempt=1
  ok=0
  while [[ $attempt -le 3 ]]; do
    if python3 scripts/escalate_to_gpt52_web.py --question "$q" --answer "$a"; then
      ok=1
      break
    fi
    echo "Escalation web call failed for ${id} (attempt ${attempt}/3)." >&2
    attempt=$((attempt + 1))
    sleep 3
  done

  if [[ $ok -eq 1 ]]; then
    # Treat placeholder or empty captures as failure and keep pending.
    answer_body_raw="$(tail -n +6 "$a" 2>/dev/null || true)"
    answer_body="$(printf '%s' "$answer_body_raw" | tr -d '[:space:]')"
    if [[ -z "$answer_body" || "$answer_body" == "ChatGPTsaid:" ]]; then
      echo "Escalation answer for ${id} appears empty; leaving pending file." >&2
      rm -f "$a"
      continue
    fi
    if printf '%s' "$answer_body_raw" | head -n 1 | grep -qi '^You said:'; then
      echo "Escalation answer for ${id} echoes user prompt; leaving pending file." >&2
      rm -f "$a"
      continue
    fi

    codex exec \
      --dangerously-bypass-approvals-and-sandbox \
      -m gpt-5.3-codex \
      -c model_reasoning_effort='"xhigh"' \
      -C "$ROOT" \
      "Read ${a}. Implement concrete code changes in this repo to address the escalation. Run tests. Write a concise execution report to ${action}." || true

    python3 -m pytest -q >> "$action" 2>&1 || true
    mv "$q" "${q}.done"
  else
    echo "Escalation failed for ${id} after retries; leaving pending file." >&2
  fi
done

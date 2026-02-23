#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEMO_DIR="$ROOT/.demo"

kill_from_file() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    return
  fi
  local pid
  pid="$(cat "$file")"
  if [[ -n "${pid:-}" ]] && kill -0 "$pid" >/dev/null 2>&1; then
    kill "$pid" >/dev/null 2>&1 || true
  fi
  rm -f "$file"
}

kill_from_file "$DEMO_DIR/tunnel.pid"
kill_from_file "$DEMO_DIR/api.pid"

echo "Stopped public demo processes (if running)."

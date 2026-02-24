#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DEMO_DIR="$ROOT/.demo"
mkdir -p "$DEMO_DIR"

API_PORT="${API_PORT:-8001}"
SITE_URL="${SITE_URL:-https://zhouyi-xiaoxiao.github.io/biopath-platform/}"

API_LOG="$DEMO_DIR/api.log"
API_PID_FILE="$DEMO_DIR/api.pid"
TUNNEL_LOG="$DEMO_DIR/tunnel.log"
TUNNEL_PID_FILE="$DEMO_DIR/tunnel.pid"
TUNNEL_URL_FILE="$DEMO_DIR/tunnel_url.txt"

is_pid_running() {
  local pid="$1"
  kill -0 "$pid" >/dev/null 2>&1
}

read_pid_file() {
  local file="$1"
  if [[ -f "$file" ]]; then
    cat "$file"
  fi
}

start_api() {
  local api_pid
  api_pid="$(read_pid_file "$API_PID_FILE" || true)"

  if [[ -n "${api_pid:-}" ]] && is_pid_running "$api_pid"; then
    return
  fi

  # If port is already in use by another process, trust it as the API process.
  if lsof -nP -iTCP:"$API_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    lsof -nP -t -iTCP:"$API_PORT" -sTCP:LISTEN | head -n1 > "$API_PID_FILE" || true
    return
  fi

  nohup python3 -m uvicorn api.main:app --host 127.0.0.1 --port "$API_PORT" >"$API_LOG" 2>&1 &
  echo $! > "$API_PID_FILE"

  for _ in {1..30}; do
    if curl -fsS "http://127.0.0.1:${API_PORT}/" >/dev/null 2>&1; then
      return
    fi
    sleep 1
  done

  echo "Failed to start API. Check $API_LOG" >&2
  exit 1
}

start_tunnel() {
  local tunnel_pid
  tunnel_pid="$(read_pid_file "$TUNNEL_PID_FILE" || true)"
  local cached_url=""
  if [[ -f "$TUNNEL_URL_FILE" ]]; then
    cached_url="$(cat "$TUNNEL_URL_FILE")"
  fi

  if [[ -n "${tunnel_pid:-}" ]] && is_pid_running "$tunnel_pid" && [[ "$cached_url" =~ ^https://[A-Za-z0-9.-]+\.lhr\.life$ ]]; then
    return
  fi

  : > "$TUNNEL_LOG"
  # Use script(1) to force a pseudo terminal so localhost.run prints the tunnel URL.
  nohup script -q "$TUNNEL_LOG" ssh -tt \
    -o StrictHostKeyChecking=no \
    -o ServerAliveInterval=30 \
    -o ExitOnForwardFailure=yes \
    -R 80:127.0.0.1:"$API_PORT" \
    nokey@localhost.run >/dev/null 2>&1 &
  echo $! > "$TUNNEL_PID_FILE"

  local url=""
  for _ in {1..45}; do
    url="$(rg -o --no-line-number 'https://[A-Za-z0-9.-]+\.lhr\.life' "$TUNNEL_LOG" | head -n1 || true)"
    if [[ -n "$url" ]]; then
      break
    fi
    sleep 1
  done

  if [[ -z "$url" ]]; then
    echo "Failed to create tunnel. Check $TUNNEL_LOG" >&2
    exit 1
  fi

  echo "$url" > "$TUNNEL_URL_FILE"
}

main() {
  start_api
  start_tunnel

  local api_url
  api_url="$(cat "$TUNNEL_URL_FILE")"

  local stage_url
  stage_url="${SITE_URL}?api=${api_url}"

  local rehearsal_url
  rehearsal_url="${SITE_URL}?api=${api_url}&tour=1"

  cat <<MSG
BioPath public demo is ready.

API URL:
${api_url}

Stage URL (recommended for live pitch):
${stage_url}

Rehearsal URL (opens guided tour):
${rehearsal_url}

Logs:
- API: ${API_LOG}
- Tunnel: ${TUNNEL_LOG}

To stop all demo processes:
  bash scripts/stop_public_demo.sh
MSG
}

main "$@"

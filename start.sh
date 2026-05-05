#!/usr/bin/env bash
# OPS Agent — one-command launcher
#   ./start.sh            # start backend + frontend
#   ./start.sh --backend  # backend only
#   ./start.sh --frontend # frontend only
#   ./start.sh --stop     # kill anything still running
#
# Backend: FastAPI on http://localhost:8000
# Frontend: Vite dev server on http://localhost:5173 (proxies /api → :8000)

set -e
cd "$(dirname "$0")"

# ---------- colors ----------
if [ -t 1 ]; then
  C_OK="\033[32m"; C_WARN="\033[33m"; C_ERR="\033[31m"; C_DIM="\033[2m"; C_RST="\033[0m"
else
  C_OK=""; C_WARN=""; C_ERR=""; C_DIM=""; C_RST=""
fi
say() { printf "%b[ops]%b %s\n" "$C_DIM" "$C_RST" "$*"; }
ok()  { printf "%b[ops]%b %s\n" "$C_OK"  "$C_RST" "$*"; }
warn(){ printf "%b[ops]%b %s\n" "$C_WARN" "$C_RST" "$*"; }
err() { printf "%b[ops]%b %s\n" "$C_ERR" "$C_RST" "$*" 1>&2; }

# ---------- args ----------
MODE="all"
case "${1:-}" in
  --backend|-b)  MODE="backend" ;;
  --frontend|-f) MODE="frontend" ;;
  --stop|-s)     MODE="stop" ;;
  -h|--help)
    cat <<EOF
Usage: ./start.sh [option]
  (no args)     start backend + frontend
  --backend     backend only (FastAPI on :8000)
  --frontend    frontend only (Vite on :5173)
  --stop        kill anything bound to :8000 / :5173
  --help        this message

Env (read from .env):
  LLM_PROVIDER  ollama | groq | openai | mock
EOF
    exit 0
    ;;
esac

# ---------- helpers ----------
kill_port() {
  local port=$1
  local pids
  pids=$(lsof -ti tcp:"$port" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    say "killing PIDs on port $port: $pids"
    kill $pids 2>/dev/null || true
    sleep 1
    pids=$(lsof -ti tcp:"$port" 2>/dev/null || true)
    if [ -n "$pids" ]; then kill -9 $pids 2>/dev/null || true; fi
  fi
}

if [ "$MODE" = "stop" ]; then
  kill_port 8000
  kill_port 5173
  ok "stopped."
  exit 0
fi

# ---------- preflight ----------
if [ "$MODE" = "all" ] || [ "$MODE" = "backend" ]; then
  if ! command -v python3 >/dev/null; then err "python3 not found"; exit 1; fi
  if ! python3 -c "import fastapi, uvicorn" 2>/dev/null; then
    warn "FastAPI/uvicorn missing — installing from requirements.txt"
    python3 -m pip install -q -r requirements.txt
  fi
fi

if [ "$MODE" = "all" ] || [ "$MODE" = "frontend" ]; then
  if ! command -v npm >/dev/null; then err "npm not found"; exit 1; fi
  if [ ! -d frontend/node_modules ]; then
    say "installing frontend deps (one-time)"
    (cd frontend && npm install --silent)
  fi
fi

# ---------- launch ----------
PIDS=()
cleanup() {
  echo
  say "shutting down…"
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  # Give children a moment, then nuke ports.
  sleep 0.5
  kill_port 8000 >/dev/null 2>&1 || true
  kill_port 5173 >/dev/null 2>&1 || true
  ok "stopped."
}
trap cleanup INT TERM EXIT

# Free ports first so re-runs don't conflict
[ "$MODE" != "frontend" ] && kill_port 8000
[ "$MODE" != "backend" ]  && kill_port 5173

if [ "$MODE" = "all" ] || [ "$MODE" = "backend" ]; then
  ok "backend  → http://localhost:8000  (FastAPI)"
  uvicorn api.server:app --port 8000 --host 127.0.0.1 \
    2>&1 | sed -u 's/^/[backend ] /' &
  PIDS+=($!)
fi

if [ "$MODE" = "all" ] || [ "$MODE" = "frontend" ]; then
  ok "frontend → http://localhost:5173 (Vite)"
  (cd frontend && npm run dev --silent) \
    2>&1 | sed -u 's/^/[frontend] /' &
  PIDS+=($!)
fi

ok "Ctrl-C to stop. Logs are interleaved below."
echo
wait

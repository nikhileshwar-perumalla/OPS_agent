#!/usr/bin/env bash
# Launch FastAPI backend + Vite frontend.
# Backend at :8000, frontend at :5173 (proxies /api → :8000).
set -e

cd "$(dirname "$0")"

# Start backend
echo "[ops] starting FastAPI on :8000"
uvicorn api.server:app --reload --port 8000 &
BACK_PID=$!

# Frontend
if [ ! -d frontend/node_modules ]; then
  echo "[ops] installing frontend deps"
  (cd frontend && npm install)
fi

echo "[ops] starting Vite on :5173"
(cd frontend && npm run dev) &
FRONT_PID=$!

trap "kill $BACK_PID $FRONT_PID 2>/dev/null" EXIT
wait

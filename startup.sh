#!/usr/bin/env bash
# Compatibility shim — the project now uses FastAPI + React (Vite).
# Forwards all args to ./start.sh.
exec "$(dirname "$0")/start.sh" "$@"

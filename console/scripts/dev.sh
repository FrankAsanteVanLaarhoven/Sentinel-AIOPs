#!/usr/bin/env bash
# Start the Sentinel engine (:8008) and the Console (:3000) together.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENGINE="$(cd "$HERE/../engine" && pwd)"

echo "▸ Sentinel engine  →  http://127.0.0.1:8008  (${DATA_SOURCE:-demo})"
(
  cd "$ENGINE"
  PYTHONPATH=src DATA_SOURCE="${DATA_SOURCE:-demo}" \
    uvicorn sentinel.api.engine_api:app --port 8008 --host 127.0.0.1 --reload
) &
ENGINE_PID=$!
trap 'kill "$ENGINE_PID" 2>/dev/null || true' EXIT

echo "▸ Sentinel Console →  http://localhost:3000"
cd "$HERE"
npm run dev

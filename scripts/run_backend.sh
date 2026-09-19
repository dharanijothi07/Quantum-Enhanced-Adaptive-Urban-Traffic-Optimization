#!/usr/bin/env bash
set -e
echo "========================================================"
echo "Starting QuantumFlow FastAPI + WebSocket Backend Engine"
echo "========================================================"
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." >/dev/null 2>&1 && pwd )"
cd "$DIR"
source venv/bin/activate || source venv/Scripts/activate
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

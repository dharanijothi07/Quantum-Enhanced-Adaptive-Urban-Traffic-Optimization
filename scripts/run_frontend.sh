#!/usr/bin/env bash
set -e
echo "========================================================"
echo "Starting QuantumFlow Vite + React Dashboard (Port 5173)"
echo "========================================================"
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/../frontend" >/dev/null 2>&1 && pwd )"
cd "$DIR"
npm run dev

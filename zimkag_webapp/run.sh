#!/usr/bin/env bash
# ZimKAG launcher — macOS / Linux
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f .env && -f .env.example ]]; then
  cp .env.example .env
  echo "[setup] Created .env from .env.example — add your GROQ_API_KEY before re-running."
fi

if [[ ! -d .venv ]]; then
  echo "[setup] Creating virtual environment..."
  python3 -m venv .venv
  source .venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
else
  source .venv/bin/activate
fi

echo
echo "──────────────────────────────────────────────────────"
echo " ZimKAG starting at http://127.0.0.1:8000"
echo " Press Ctrl+C to stop."
echo "──────────────────────────────────────────────────────"
echo

python -m backend.app

#!/usr/bin/env bash
# ZimKAG Email Watcher — macOS / Linux launcher
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f .env && -f .env.example ]]; then
  cp .env.example .env
  echo "[setup] Created .env from .env.example — review settings before continuing."
fi

if [[ ! -f credentials/client_secret.json ]]; then
  cat <<EOF

[error] Missing credentials/client_secret.json

Follow the 5-minute setup in credentials/README.md to create one.
Without it the watcher cannot authenticate with Gmail.
EOF
  exit 1
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
echo " ZimKAG Email Watcher starting..."
echo " First run will open your browser to grant Gmail access."
echo " Press Ctrl+C to stop."
echo "──────────────────────────────────────────────────────"
echo

python -m zimkag_email_watcher.watcher

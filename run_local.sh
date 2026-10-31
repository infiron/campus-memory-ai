#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT/backend"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.11+ is required. Install Python, then run this script again." >&2
  exit 1
fi
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck source=/dev/null
source .venv/bin/activate
if [ ! -f .env ]; then
  cp .env.example .env
fi
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo
echo "Starting Campus Memory AI at http://127.0.0.1:8000"
echo "Press Ctrl+C to stop the server."
exec python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

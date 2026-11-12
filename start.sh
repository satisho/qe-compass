#!/usr/bin/env bash
# QE Compass launcher for macOS and Linux.
set -euo pipefail
cd "$(dirname "$0")"

PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "QE Compass needs Python 3.10 or newer. Install it from https://www.python.org/downloads/ and run ./start.sh again."
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  echo "Setting up QE Compass for first use. This takes a minute..."
  "$PY" -m venv .venv
fi
if ! cmp -s backend/requirements.txt .venv/installed-requirements.txt; then
  echo "Installing components..."
  .venv/bin/python -m pip install --disable-pip-version-check -q -r backend/requirements.txt
  cp backend/requirements.txt .venv/installed-requirements.txt
fi

cd backend
exec ../.venv/bin/python -m app --open "$@"

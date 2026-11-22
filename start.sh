#!/usr/bin/env bash
# Starts the DSA Tracker, setting everything up on first run.
set -euo pipefail

cd "$(dirname "$0")"

PY="venv/bin/python"

if [ ! -x "$PY" ]; then
    echo "Setting up for first use. This takes a minute, only happens once."
    echo

    if command -v python3 >/dev/null 2>&1; then
        BOOTSTRAP=python3
    elif command -v python >/dev/null 2>&1; then
        BOOTSTRAP=python
    else
        echo "Python was not found on this machine."
        echo "Install Python 3.12 or newer from https://www.python.org/downloads/"
        exit 1
    fi

    "$BOOTSTRAP" -m venv venv
    "$PY" -m pip install --upgrade pip --quiet
    "$PY" -m pip install -r requirements.txt --quiet

    echo "Setup complete."
    echo
fi

echo "Starting DSA Tracker at http://localhost:8000"
echo "Press Ctrl+C to stop it."
echo
exec "$PY" app.py

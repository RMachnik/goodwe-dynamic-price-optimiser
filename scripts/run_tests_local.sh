#!/usr/bin/env bash
# Local test runner for development
# Creates a venv (if missing), installs requirements, and runs pytest

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$ROOT_DIR/venv"

if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtualenv at $VENV_DIR..."
  python3 -m venv "$VENV_DIR"
fi

echo "Activating venv..."
source "$VENV_DIR/bin/activate"

echo "Upgrading pip and installing requirements..."
pip install --upgrade pip
pip install -r "$ROOT_DIR/requirements.txt"

echo "Running pytest..."
python -m pytest -q

deactivate || true

echo "Tests completed."

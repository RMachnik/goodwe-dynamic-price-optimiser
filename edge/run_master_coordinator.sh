#!/bin/bash
# Wrapper script for running master coordinator as systemd service

# Set up environment
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$PROJECT_ROOT/src"
export PYTHONUNBUFFERED=1

# Use virtual environment Python directly
# Executing within the venv automatically handles the correct site-packages
exec "$PROJECT_ROOT/venv/bin/python" "$PROJECT_ROOT/src/master_coordinator.py" --non-interactive
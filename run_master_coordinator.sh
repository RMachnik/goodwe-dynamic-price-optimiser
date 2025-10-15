#!/bin/bash
# Wrapper script for running master coordinator as systemd service

# Set up environment
export PYTHONPATH="/home/rmachnik/sources/goodwe-dynamic-price-optimiser/src:/home/rmachnik/sources/goodwe-dynamic-price-optimiser/venv/lib/python3.12/site-packages"
export PYTHONUNBUFFERED=1
export HOME="/home/rmachnik"
export USER="rmachnik"

# Change to the correct directory (stay in project root, not src)
cd /home/rmachnik/sources/goodwe-dynamic-price-optimiser

# Use virtual environment Python directly
exec /home/rmachnik/sources/goodwe-dynamic-price-optimiser/venv/bin/python src/master_coordinator.py --non-interactive
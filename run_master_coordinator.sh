#!/bin/bash
# Wrapper script for running master coordinator as systemd service

# Set up environment
export PYTHONPATH="/home/rmachnik/sources/goodwe-dynamic-price-optimiser/src:/home/rmachnik/sources/goodwe-dynamic-price-optimiser/venv/lib/python3.12/site-packages"
export PYTHONUNBUFFERED=1
export HOME="/home/rmachnik"
export USER="rmachnik"

# Change to the correct directory
cd /home/rmachnik/sources/goodwe-dynamic-price-optimiser/src

# Activate virtual environment and run
source /home/rmachnik/sources/goodwe-dynamic-price-optimiser/venv/bin/activate
exec python master_coordinator.py --non-interactive
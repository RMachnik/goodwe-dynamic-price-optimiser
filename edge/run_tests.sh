#!/bin/bash
cd /Users/rafalmachnik/sources/goodwe-dynamic-price-optimiser
.venv/bin/python -m pytest -v --tb=short 2>&1 | head -500

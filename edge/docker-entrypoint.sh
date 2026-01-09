#!/bin/bash
set -e

# Docker entrypoint for GoodWe Dynamic Price Optimiser
# Handles proper initialization and signal handling

echo "🐳 Starting GoodWe Dynamic Price Optimiser..."

# Function to handle shutdown gracefully
shutdown_handler() {
    echo "🛑 Received shutdown signal, stopping gracefully..."
    # Kill the main process
    kill -TERM "$child" 2>/dev/null || true
    # Wait for it to finish
    wait "$child"
    echo "✅ Shutdown complete"
    exit 0
}

# Set up signal handlers
trap shutdown_handler SIGTERM SIGINT

# Ensure required directories exist
mkdir -p /app/data/energy_data
mkdir -p /app/logs
mkdir -p /app/out
mkdir -p /app/config

# Check if config file exists
if [ ! -f "/app/config/master_coordinator_config.yaml" ]; then
    echo "⚠️  Warning: master_coordinator_config.yaml not found in /app/config/"
    echo "   Please mount your configuration file to /app/config/"
    echo "   Example: -v /host/path/config:/app/config"
fi

# Python path is set by docker-compose environment variables

# Log startup information
echo "📁 Working directory: $(pwd)"
echo "📁 Data directory: /app/data"
echo "📁 Logs directory: /app/logs"
echo "📁 Config directory: /app/config"
echo "🐍 Python version: $(python --version)"
echo "📦 Python path: $PYTHONPATH"

# Start the main application
echo "🚀 Starting master coordinator..."
exec "$@"

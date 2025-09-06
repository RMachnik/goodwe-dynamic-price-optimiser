#!/bin/bash

# Docker Run Script for GoodWe Dynamic Price Optimiser
# This script uses the working docker run command instead of docker-compose

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CONTAINER_NAME="goodwe-dynamic-price-optimiser"
IMAGE_NAME="goodwe-dynamic-price-optimiser:latest"
CONFIG_DIR="$(pwd)/config"
DATA_DIR="$(pwd)/data"
LOGS_DIR="$(pwd)/logs"
OUT_DIR="$(pwd)/out"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to create necessary directories
create_directories() {
    print_status "Creating necessary directories..."
    mkdir -p "$DATA_DIR" "$LOGS_DIR" "$OUT_DIR"
    print_success "Directories created"
}

# Function to check if container is running
is_container_running() {
    docker ps --format "table {{.Names}}" | grep -q "^${CONTAINER_NAME}$"
}

# Function to start container
start_container() {
    if is_container_running; then
        print_warning "Container is already running"
        return 0
    fi
    
    print_status "Starting container..."
    docker run -d \
        --name "$CONTAINER_NAME" \
        --restart unless-stopped \
        -e PYTHONPATH=/app/src \
        -e TZ=Europe/Warsaw \
        -e LOG_LEVEL=INFO \
        -e CONFIG_PATH=/app/config/master_coordinator_config.yaml \
        -v "$CONFIG_DIR:/app/config:ro" \
        -v "$DATA_DIR:/app/data" \
        -v "$LOGS_DIR:/app/logs" \
        -v "$OUT_DIR:/app/out" \
        --network host \
        "$IMAGE_NAME"
    
    print_success "Container started successfully"
}

# Function to stop container
stop_container() {
    if ! is_container_running; then
        print_warning "Container is not running"
        return 0
    fi
    
    print_status "Stopping container..."
    docker stop "$CONTAINER_NAME"
    docker rm "$CONTAINER_NAME"
    print_success "Container stopped"
}

# Function to show container status
show_status() {
    if is_container_running; then
        print_success "Container is running"
        docker ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    else
        print_warning "Container is not running"
    fi
}

# Function to show logs
show_logs() {
    if is_container_running; then
        docker logs "$CONTAINER_NAME" --tail 50 -f
    else
        print_error "Container is not running"
        exit 1
    fi
}

# Function to show help
show_help() {
    echo "GoodWe Dynamic Price Optimiser - Docker Run Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  start     Start the container"
    echo "  stop      Stop the container"
    echo "  restart   Restart the container"
    echo "  status    Show container status"
    echo "  logs      Show container logs"
    echo "  shell     Open shell in container"
    echo "  help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start"
    echo "  $0 logs"
    echo "  $0 status"
}

# Main script logic
case "${1:-help}" in
    start)
        create_directories
        start_container
        show_status
        ;;
    stop)
        stop_container
        ;;
    restart)
        stop_container
        create_directories
        start_container
        show_status
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    shell)
        if is_container_running; then
            docker exec -it "$CONTAINER_NAME" /bin/bash
        else
            print_error "Container is not running"
            exit 1
        fi
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac

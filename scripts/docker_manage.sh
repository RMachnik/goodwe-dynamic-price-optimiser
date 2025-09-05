#!/bin/bash
# Docker Management Script for GoodWe Dynamic Price Optimiser
# Usage: ./docker_manage.sh [build|start|stop|restart|logs|status|clean|shell]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project name
PROJECT_NAME="goodwe-dynamic-price-optimiser"
CONTAINER_NAME="goodwe-dynamic-price-optimiser"

# Log function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if Docker is running
check_docker() {
    if ! docker info >/dev/null 2>&1; then
        error "Docker is not running. Please start Docker first."
        exit 1
    fi
}

# Create necessary directories
create_directories() {
    log "Creating necessary directories..."
    mkdir -p data logs out
    success "Directories created"
}

# Build the Docker image
build_image() {
    log "Building Docker image with BuildKit..."
    export DOCKER_BUILDKIT=1
    export COMPOSE_DOCKER_CLI_BUILD=1
    docker buildx build --platform linux/arm64 -t $PROJECT_NAME:latest .
    success "Docker image built successfully"
}

# Start the container
start_container() {
    log "Starting container..."
    
    # Check if container is already running
    if docker ps -q -f name=$CONTAINER_NAME | grep -q .; then
        warning "Container is already running"
        return 0
    fi
    
    # Start with docker-compose
    docker-compose up -d
    success "Container started successfully"
    
    # Show status
    show_status
}

# Stop the container
stop_container() {
    log "Stopping container..."
    docker-compose down
    success "Container stopped"
}

# Restart the container
restart_container() {
    log "Restarting container..."
    stop_container
    sleep 2
    start_container
}

# Show container logs
show_logs() {
    log "Showing container logs..."
    docker-compose logs -f
}

# Show container status
show_status() {
    log "Container status:"
    echo ""
    docker-compose ps
    echo ""
    
    if docker ps -q -f name=$CONTAINER_NAME | grep -q .; then
        success "Container is running"
        echo ""
        log "Container details:"
        docker ps -f name=$CONTAINER_NAME --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    else
        warning "Container is not running"
    fi
}

# Clean up Docker resources
clean_docker() {
    log "Cleaning up Docker resources..."
    
    # Stop and remove containers
    docker-compose down --remove-orphans
    
    # Remove unused images
    docker image prune -f
    
    # Remove unused volumes (be careful!)
    read -p "Remove unused volumes? This will delete all unused Docker volumes! (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker volume prune -f
        success "Unused volumes removed"
    else
        log "Skipping volume cleanup"
    fi
    
    success "Docker cleanup completed"
}

# Open shell in container
open_shell() {
    log "Opening shell in container..."
    if docker ps -q -f name=$CONTAINER_NAME | grep -q .; then
        docker exec -it $CONTAINER_NAME /bin/bash
    else
        error "Container is not running. Start it first with: $0 start"
        exit 1
    fi
}

# Show help
show_help() {
    echo "Docker Management Script for GoodWe Dynamic Price Optimiser"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  build     Build the Docker image"
    echo "  start     Start the container"
    echo "  stop      Stop the container"
    echo "  restart   Restart the container"
    echo "  logs      Show container logs"
    echo "  status    Show container status"
    echo "  shell     Open shell in container"
    echo "  clean     Clean up Docker resources"
    echo "  help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 build && $0 start"
    echo "  $0 logs -f"
    echo "  $0 shell"
}

# Main script logic
main() {
    check_docker
    create_directories
    
    case "${1:-help}" in
        build)
            build_image
            ;;
        start)
            start_container
            ;;
        stop)
            stop_container
            ;;
        restart)
            restart_container
            ;;
        logs)
            show_logs
            ;;
        status)
            show_status
            ;;
        shell)
            open_shell
            ;;
        clean)
            clean_docker
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            error "Unknown command: $1"
            show_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@"

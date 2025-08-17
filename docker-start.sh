#!/bin/bash

# Enhanced RAG Docker Startup Script
# This script helps developers start the containerized application easily

set -e

echo "🚀 Starting Enhanced RAG Application with Docker"
echo "================================================"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop first."
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose not found. Please install Docker Compose."
    exit 1
fi

# Parse command line arguments
MODE="production"
REBUILD=false
LOGS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --dev|--development)
            MODE="development"
            shift
            ;;
        --rebuild)
            REBUILD=true
            shift
            ;;
        --logs)
            LOGS=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dev, --development    Start in development mode"
            echo "  --rebuild              Force rebuild of containers"
            echo "  --logs                 Show logs after startup"
            echo "  --help, -h             Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                     # Start in production mode"
            echo "  $0 --dev               # Start in development mode"
            echo "  $0 --rebuild --logs    # Rebuild and show logs"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo "📋 Configuration:"
echo "   Mode: $MODE"
echo "   Rebuild: $REBUILD"
echo "   Show logs: $LOGS"
echo ""

# Set compose files based on mode
COMPOSE_FILES="-f docker-compose.yml"
if [ "$MODE" = "development" ]; then
    COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.override.yml"
fi

# Stop existing containers
echo "🛑 Stopping existing containers..."
docker-compose $COMPOSE_FILES down --remove-orphans

# Build containers if needed
if [ "$REBUILD" = true ]; then
    echo "🔨 Rebuilding containers..."
    docker-compose $COMPOSE_FILES build --no-cache
else
    echo "🔨 Building containers..."
    docker-compose $COMPOSE_FILES build
fi

# Start services
echo "🚀 Starting services..."
docker-compose $COMPOSE_FILES up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check service health
echo "🏥 Checking service health..."

# Check backend health
for i in {1..30}; do
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ Backend is healthy"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Backend health check failed"
        docker-compose $COMPOSE_FILES logs backend
        exit 1
    fi
    sleep 2
done

# Check frontend
for i in {1..30}; do
    if curl -f http://localhost > /dev/null 2>&1; then
        echo "✅ Frontend is healthy"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Frontend health check failed"
        docker-compose $COMPOSE_FILES logs frontend
        exit 1
    fi
    sleep 2
done

# Check Qdrant
for i in {1..30}; do
    if curl -f http://localhost:6333/dashboard > /dev/null 2>&1; then
        echo "✅ Qdrant is healthy"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Qdrant health check failed"
        docker-compose $COMPOSE_FILES logs qdrant
        exit 1
    fi
    sleep 2
done

# Check Ollama
for i in {1..30}; do
    if curl -f http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "✅ Ollama is healthy"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Ollama health check failed"
        docker-compose $COMPOSE_FILES logs ollama
        exit 1
    fi
    sleep 2
done

echo ""
echo "🎉 All services are running successfully!"
echo ""
echo "📱 Application URLs:"
echo "   Frontend:        http://localhost"
echo "   Backend API:     http://localhost:8000"
echo "   API Docs:        http://localhost:8000/docs"
echo "   Qdrant Dashboard: http://localhost:6333/dashboard"
echo "   Ollama API:      http://localhost:11434"
echo ""
echo "💡 Useful commands:"
echo "   View logs:       docker-compose $COMPOSE_FILES logs -f"
echo "   Stop services:   docker-compose $COMPOSE_FILES down"
echo "   Service status:  docker-compose $COMPOSE_FILES ps"
echo ""

# Show logs if requested
if [ "$LOGS" = true ]; then
    echo "📋 Showing service logs (Ctrl+C to exit):"
    docker-compose $COMPOSE_FILES logs -f
fi

echo "🚀 Setup complete! Your Enhanced RAG application is ready to use."
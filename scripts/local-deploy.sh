#!/bin/bash

# VCC 3 - Local Docker Compose Deployment
# Spins up local VM backend with Ollama and FastAPI using Docker Compose

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "======================================"
echo "VCC 3 - Local Docker Deployment"
echo "======================================"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker not found. Please install Docker Desktop."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "ERROR: docker-compose not found. Please install Docker Compose."
    exit 1
fi

# Start services
echo "[1/3] Starting Docker Compose services..."
docker-compose up -d

echo "[2/3] Waiting for services to be ready..."
sleep 10

# Check health
echo "[3/3] Verifying service health..."
HEALTH_CHECK=$(curl -s http://127.0.0.1:8000/api/health || echo "{}")

if echo "$HEALTH_CHECK" | grep -q "ok"; then
    echo "✓ Backend is running"
else
    echo "✗ Backend health check failed"
    echo "Output: $HEALTH_CHECK"
    exit 1
fi

# Try to pull Ollama model
echo ""
echo "======================================"
echo "Setting up local LLM..."
echo "======================================"
echo "Pulling llama3.2:1b model (~2GB)..."

OLLAMA_CONTAINER=$(docker-compose ps -q ollama)
if [[ -z "$OLLAMA_CONTAINER" ]]; then
    echo "ERROR: Ollama container not running"
    exit 1
fi

docker exec "$OLLAMA_CONTAINER" ollama pull llama3.2:1b || {
    echo "Note: Model pull in progress. This takes 1-5 min depending on internet."
    echo "You can monitor with: docker logs vcc-ollama"
}

echo ""
echo "======================================"
echo "VCC 3 Local Deployment Ready!"
echo "======================================"
echo "➜ Frontend:     http://127.0.0.1:8000"
echo "➜ API Health:   http://127.0.0.1:8000/api/health"
echo "➜ Metrics:      http://127.0.0.1:8000/api/metrics"
echo ""
echo "Docker commands:"
echo "  View logs:    docker-compose logs -f"
echo "  Stop:         docker-compose down"
echo "  Restart:      docker-compose restart"
echo ""
echo "To test classification:"
echo "  curl -X POST http://127.0.0.1:8000/api/classify -H 'Content-Type: application/json' -d '{\"text\":\"This is great!\"}'"
echo ""
echo "Open http://127.0.0.1:8000 in your browser and try the UI!"
echo "======================================"

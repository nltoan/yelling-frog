#!/bin/bash

# Quick Start Script for Web Crawler
# This script sets up and runs the crawler in Docker

set -e

echo "=========================================="
echo "🕷️  Web Crawler - Quick Start"
echo "=========================================="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running"
    echo "Please start Docker and try again"
    exit 1
fi

echo "✓ Docker is running"

# Check if container exists
if docker ps -a | grep -q webcrawler-dev; then
    echo "✓ Container exists"

    # Start if stopped
    if ! docker ps | grep -q webcrawler-dev; then
        echo "▶ Starting container..."
        docker start webcrawler-dev
    fi
else
    echo "▶ Building and creating container..."
    docker build -t webcrawler:dev .
    docker run -d --name webcrawler-dev -p 8000:8000 webcrawler:dev tail -f /dev/null
fi

# Create data directories
echo "▶ Creating data directories..."
docker exec webcrawler-dev mkdir -p /app/data /tmp

# Install dependencies
echo "▶ Installing dependencies (this may take a minute)..."
docker exec webcrawler-dev pip install -q -r /app/requirements.txt

# Run integration test
echo ""
echo "=========================================="
echo "🧪 Running Integration Test"
echo "=========================================="
docker exec webcrawler-dev python /app/test_integration.py

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✅ Integration Test Passed!"
    echo "=========================================="
else
    echo ""
    echo "=========================================="
    echo "❌ Integration Test Failed"
    echo "=========================================="
    exit 1
fi

# Start the server
echo ""
echo "=========================================="
echo "🚀 Starting Web Server"
echo "=========================================="
echo ""
echo "Server will start in background..."
echo "Access the application at:"
echo ""
echo "  📱 Web UI:   http://localhost:8000/"
echo "  🔌 API:      http://localhost:8000/api"
echo "  📚 API Docs: http://localhost:8000/api/docs"
echo ""
echo "=========================================="

# Kill any existing server process
docker exec webcrawler-dev pkill -f "python /app/run_server.py" || true

# Start server in background
docker exec -d webcrawler-dev python /app/run_server.py

# Wait for server to start
echo "⏳ Waiting for server to start..."
sleep 3

# Check if server is running
if docker exec webcrawler-dev curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "✅ Server is running!"
    echo ""
    echo "=========================================="
    echo "🎉 Ready to Crawl!"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "  1. Open http://localhost:8000/ in your browser"
    echo "  2. Enter a URL to crawl (e.g., https://example.com)"
    echo "  3. Click 'Start Crawl'"
    echo "  4. Watch real-time progress"
    echo "  5. Apply filters and export data"
    echo ""
    echo "To stop the server:"
    echo "  docker exec webcrawler-dev pkill -f run_server.py"
    echo ""
    echo "To stop the container:"
    echo "  docker stop webcrawler-dev"
    echo ""
    echo "=========================================="
else
    echo "⚠️  Server may still be starting..."
    echo "Wait a few seconds and try: http://localhost:8000/"
fi

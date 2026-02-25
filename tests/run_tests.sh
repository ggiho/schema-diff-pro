#!/bin/bash

# Test runner script for Schema Diff Pro
echo "🧪 Running Schema Diff Pro Tests"
echo "=================================="

# Check if we're in Docker or local environment
if [ "$DOCKER_ENV" = "true" ]; then
    echo "🐳 Running in Docker environment"
    API_BASE_URL="http://backend:8000"
else
    echo "💻 Running in local environment"  
    API_BASE_URL="http://localhost:8000"
fi

echo "🌐 API Base URL: $API_BASE_URL"
echo ""

echo "🔧 Running Unit Tests..."
echo "========================"
cd "$(dirname "$0")"
uv run --project ../backend pytest test_environment.py -v

echo ""
echo "🌐 Running Integration Tests..."
echo "==============================="
uv run --project ../backend python test_integration.py

echo ""
echo "✅ All tests completed!"
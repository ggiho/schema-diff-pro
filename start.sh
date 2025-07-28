#!/bin/bash

echo "🚀 Starting Schema Diff Pro..."
echo ""

# Check if Redis is running
if ! docker ps | grep -q redis-schema-diff; then
    echo "📦 Starting Redis..."
    docker run -d --name redis-schema-diff -p 6379:6379 redis:7-alpine > /dev/null
fi

# Backend
echo "🔧 Starting backend server..."
cd backend
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt -q
if [ ! -f ".env" ]; then
    cp .env.example .env
fi
nohup python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
BACKEND_PID=$!
cd ..

# Frontend
echo "🎨 Starting frontend server..."
cd frontend
if [ ! -d "node_modules" ]; then
    npm install
fi
nohup npm run dev > frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

sleep 3

echo ""
echo "✅ Schema Diff Pro is running!"
echo ""
echo "   🌐 Frontend: http://localhost:3000"
echo "   🔌 Backend API: http://localhost:8000"
echo "   📚 API Docs: http://localhost:8000/docs"
echo ""
echo "📋 Logs:"
echo "   Backend: backend/backend.log"
echo "   Frontend: frontend/frontend.log"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Save PIDs
echo $BACKEND_PID > .backend.pid
echo $FRONTEND_PID > .frontend.pid

# Trap Ctrl+C
trap cleanup INT

cleanup() {
    echo ""
    echo "🛑 Stopping services..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    docker stop redis-schema-diff > /dev/null 2>&1
    rm -f .backend.pid .frontend.pid
    echo "✅ All services stopped"
    exit 0
}

# Keep script running
wait
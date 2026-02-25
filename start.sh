#!/bin/bash

echo "🚀 Starting Schema Diff Pro..."
echo ""

# Backend
echo "🔧 Starting backend server..."
cd backend
uv sync --no-dev -q
if [ ! -f ".env" ]; then
    cp .env.example .env
fi
nohup uv run uvicorn main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
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
    rm -f .backend.pid .frontend.pid
    echo "✅ All services stopped"
    exit 0
}

# Keep script running
wait
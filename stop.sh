#!/bin/bash

echo "🛑 Stopping Schema Diff Pro..."

# Kill backend
if [ -f .backend.pid ]; then
    BACKEND_PID=$(cat .backend.pid)
    kill $BACKEND_PID 2>/dev/null
    rm -f .backend.pid
    echo "✅ Backend stopped"
fi

# Kill frontend
if [ -f .frontend.pid ]; then
    FRONTEND_PID=$(cat .frontend.pid)
    kill $FRONTEND_PID 2>/dev/null
    rm -f .frontend.pid
    echo "✅ Frontend stopped"
fi

# Find and kill any remaining processes
pkill -f "uvicorn main:app" 2>/dev/null
pkill -f "npm run dev" 2>/dev/null

echo "✅ All services stopped"
from fastapi import WebSocket
from typing import Dict, Optional
import json
import logging
import asyncio

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manage WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.comparison_tasks: Dict[str, asyncio.Task] = {}
    
    async def connect(self, websocket: WebSocket, comparison_id: str):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        self.active_connections[comparison_id] = websocket
        logger.info(f"WebSocket connected for comparison {comparison_id}")
        
        # Send initial connection confirmation
        await self.send_message(comparison_id, {
            "type": "connected",
            "comparison_id": comparison_id,
            "message": "Connected to comparison progress stream"
        })
    
    def disconnect(self, comparison_id: str):
        """Remove a WebSocket connection"""
        if comparison_id in self.active_connections:
            del self.active_connections[comparison_id]
            logger.info(f"WebSocket disconnected for comparison {comparison_id}")
        
        # Cancel any running comparison task
        if comparison_id in self.comparison_tasks:
            task = self.comparison_tasks[comparison_id]
            if not task.done():
                task.cancel()
            del self.comparison_tasks[comparison_id]
    
    async def send_message(self, comparison_id: str, message: dict):
        """Send a message to a specific connection"""
        websocket = self.active_connections.get(comparison_id)
        if websocket:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to {comparison_id}: {e}")
                self.disconnect(comparison_id)
    
    async def send_progress(self, comparison_id: str, progress: dict):
        """Send progress update"""
        await self.send_message(comparison_id, {
            "type": "progress",
            "data": progress
        })
    
    async def send_error(self, comparison_id: str, error: str):
        """Send error message"""
        await self.send_message(comparison_id, {
            "type": "error",
            "message": error
        })
    
    async def send_complete(self, comparison_id: str, result_url: str):
        """Send completion message"""
        await self.send_message(comparison_id, {
            "type": "complete",
            "result_url": result_url,
            "message": "Comparison completed successfully"
        })
    
    def register_task(self, comparison_id: str, task: asyncio.Task):
        """Register a comparison task"""
        self.comparison_tasks[comparison_id] = task
    
    async def broadcast_to_all(self, message: dict):
        """Broadcast a message to all connected clients"""
        disconnected = []
        
        for comparison_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to {comparison_id}: {e}")
                disconnected.append(comparison_id)
        
        # Clean up disconnected clients
        for comparison_id in disconnected:
            self.disconnect(comparison_id)
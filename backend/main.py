from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import uvicorn

from core.config import settings
from core.database import connection_pool
from api.routers import comparison, profiles, sync, database
from api.websockets.comparison_ws import ConnectionManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("Starting Schema Diff Pro...")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Schema Diff Pro...")
    await connection_pool.close_all()


# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connection manager
manager = ConnectionManager()

# Include routers
app.include_router(comparison.router, prefix=f"{settings.API_V1_STR}/comparison", tags=["comparison"])
app.include_router(profiles.router, prefix=f"{settings.API_V1_STR}/profiles", tags=["profiles"])
app.include_router(sync.router, prefix=f"{settings.API_V1_STR}/sync", tags=["sync"])
app.include_router(database.router, prefix=f"{settings.API_V1_STR}/database", tags=["database"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "operational"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": settings.VERSION
    }


@app.websocket("/ws/comparison/{comparison_id}")
async def websocket_endpoint(websocket: WebSocket, comparison_id: str):
    """WebSocket endpoint for real-time comparison progress"""
    try:
        await manager.connect(websocket, comparison_id)
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            # Handle any client messages if needed
            # Echo back to keep connection alive
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for {comparison_id}")
        manager.disconnect(comparison_id)
    except Exception as e:
        logger.error(f"WebSocket error for {comparison_id}: {e}")
        manager.disconnect(comparison_id)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
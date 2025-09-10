from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from typing import Optional, Dict, Any, List
import asyncio
import logging

from models.base import (
    DatabaseConfig, ComparisonOptions, ComparisonResult,
    ComparisonProgress
)
from models.ssh_tunnel import DatabaseConfigWithSSH
from services.comparison_engine import ComparisonEngine
from services.history_manager import HistoryManager
from core.config import settings
from api.websockets.comparison_ws import ConnectionManager

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory storage for results (using JSON file storage for persistence)
comparison_results: Dict[str, ComparisonResult] = {}
history_manager = HistoryManager()


@router.post("/compare")
async def start_comparison(
    source_config: DatabaseConfigWithSSH,
    target_config: DatabaseConfigWithSSH,
    options: Optional[ComparisonOptions] = None,
    background_tasks: BackgroundTasks = BackgroundTasks()
) -> Dict[str, str]:
    """Start a new database comparison"""
    if not options:
        options = ComparisonOptions()
    
    # Enhanced logging for debugging
    logger.info("=== COMPARISON REQUEST ===")
    logger.info(f"Source config: {source_config.host}:{source_config.port}/{source_config.database}")
    logger.info(f"Target config: {target_config.host}:{target_config.port}/{target_config.database}")
    logger.info(f"Source has SSH tunnel: {hasattr(source_config, 'ssh_tunnel') and source_config.ssh_tunnel and source_config.ssh_tunnel.enabled}")
    logger.info(f"Target has SSH tunnel: {hasattr(target_config, 'ssh_tunnel') and target_config.ssh_tunnel and target_config.ssh_tunnel.enabled}")
    
    # If database is specified in config, limit comparison to that schema only
    included_schemas = []
    if source_config.database:
        included_schemas.append(source_config.database)
    if target_config.database and target_config.database not in included_schemas:
        included_schemas.append(target_config.database)
    
    # Override included_schemas if database is specified
    if included_schemas:
        options.included_schemas = included_schemas
        logger.info(f"Limiting comparison to schemas: {included_schemas}")
    
    engine = ComparisonEngine()
    
    # Create a task to run the comparison
    async def run_comparison(comparison_id: str):
        try:
            # Get WebSocket manager from app state
            from main import manager
            
            result = None
            async for update in engine.compare_databases(source_config, target_config, options):
                if isinstance(update, ComparisonProgress):
                    # Send progress via WebSocket
                    await manager.send_progress(comparison_id, update.dict())
                else:
                    # Final result
                    result = update
            
            if result:
                # Store result
                comparison_results[comparison_id] = result
                
                # Add to history
                history_manager.add_comparison(
                    comparison_id,
                    source_config,
                    target_config,
                    len(result.differences),
                    result.summary
                )
                
                # Send completion via WebSocket
                await manager.send_complete(
                    comparison_id,
                    f"/api/v1/comparison/{comparison_id}/result"
                )
        
        except Exception as e:
            logger.error(f"Comparison failed: {str(e)}")
            await manager.send_error(comparison_id, str(e))
    
    # Generate comparison ID from the result generator
    # This is a bit hacky but works for the example
    comparison_id = None
    
    # Start the comparison in background
    async def start_comparison_task():
        nonlocal comparison_id
        async for update in engine.compare_databases(source_config, target_config, options):
            if isinstance(update, ComparisonProgress):
                comparison_id = update.comparison_id
                break
        
        if comparison_id:
            task = asyncio.create_task(run_comparison(comparison_id))
            from main import manager
            manager.register_task(comparison_id, task)
    
    await start_comparison_task()
    
    if not comparison_id:
        raise HTTPException(status_code=500, detail="Failed to start comparison")
    
    return {
        "comparison_id": comparison_id,
        "status": "started",
        "websocket_url": f"/ws/comparison/{comparison_id}"
    }


@router.get("/{comparison_id}/result")
async def get_comparison_result(comparison_id: str) -> ComparisonResult:
    """Get comparison result"""
    if comparison_id not in comparison_results:
        raise HTTPException(status_code=404, detail="Comparison not found")
    
    return comparison_results[comparison_id]


@router.get("/{comparison_id}/status")
async def get_comparison_status(comparison_id: str) -> Dict[str, Any]:
    """Get comparison status"""
    if comparison_id in comparison_results:
        return {
            "status": "completed",
            "result_available": True
        }
    
    # Check if task is running
    from main import manager
    if comparison_id in manager.comparison_tasks:
        task = manager.comparison_tasks[comparison_id]
        if task.done():
            return {
                "status": "failed" if task.exception() else "completed",
                "result_available": comparison_id in comparison_results
            }
        else:
            return {
                "status": "running",
                "result_available": False
            }
    
    return {
        "status": "not_found",
        "result_available": False
    }


@router.delete("/{comparison_id}")
async def cancel_comparison(comparison_id: str) -> Dict[str, str]:
    """Cancel a running comparison"""
    from main import manager
    
    if comparison_id in manager.comparison_tasks:
        task = manager.comparison_tasks[comparison_id]
        if not task.done():
            task.cancel()
            return {"status": "cancelled"}
    
    return {"status": "not_found"}


@router.get("/recent/list")
async def get_recent_comparisons(limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent comparisons"""
    return history_manager.get_recent(limit)
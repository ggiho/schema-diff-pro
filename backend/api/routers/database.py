from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import aiomysql
import logging

from models.base import DatabaseConfig

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/test")
async def test_connection(config: DatabaseConfig) -> Dict[str, Any]:
    """Test database connection and return connection info"""
    try:
        # Create connection with timeout
        connection = await aiomysql.connect(
            host=config.host,
            port=config.port,
            user=config.user,
            password=config.password,
            db=config.database if config.database else None,
            connect_timeout=5,
            autocommit=True
        )
        
        try:
            async with connection.cursor() as cursor:
                # Get MySQL version
                await cursor.execute("SELECT VERSION()")
                version = await cursor.fetchone()
                
                # Get current database
                if config.database:
                    current_db = config.database
                else:
                    await cursor.execute("SELECT DATABASE()")
                    result = await cursor.fetchone()
                    current_db = result[0] if result and result[0] else "MySQL"
                
                # Get server info
                await cursor.execute("SHOW VARIABLES LIKE 'hostname'")
                hostname_result = await cursor.fetchone()
                hostname = hostname_result[1] if hostname_result else config.host
                
                return {
                    "success": True,
                    "database": current_db,
                    "version": version[0] if version else "Unknown",
                    "host": hostname,
                    "message": f"Successfully connected to {current_db}"
                }
                
        finally:
            connection.close()
            
    except aiomysql.Error as e:
        error_msg = str(e)
        logger.error(f"Database connection test failed: {error_msg}")
        
        # Provide user-friendly error messages
        if "Access denied" in error_msg:
            detail = "Invalid username or password"
        elif "Can't connect" in error_msg:
            detail = f"Cannot connect to MySQL server at {config.host}:{config.port}"
        elif "Unknown database" in error_msg:
            detail = f"Database '{config.database}' does not exist"
        else:
            detail = f"Connection failed: {error_msg}"
            
        raise HTTPException(status_code=400, detail=detail)
        
    except Exception as e:
        logger.error(f"Unexpected error during connection test: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Unexpected error: {str(e)}"
        )
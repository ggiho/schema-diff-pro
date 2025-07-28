from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool, QueuePool
import aiomysql
from contextlib import asynccontextmanager
import logging

from .config import settings

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Async database connection manager with connection pooling"""
    
    def __init__(self, connection_url: str, database: Optional[str] = None):
        self.connection_url = connection_url
        self.database = database
        self._engine: Optional[AsyncEngine] = None
    
    async def get_engine(self) -> AsyncEngine:
        """Get or create async engine with connection pooling"""
        if self._engine is None:
            # Parse connection URL and add database if specified
            url = self.connection_url
            if self.database and "?" in url:
                url = url.split("?")[0] + f"/{self.database}?" + url.split("?")[1]
            elif self.database:
                url = f"{url}/{self.database}"
            
            # Replace mysql+pymysql with mysql+aiomysql for async
            url = url.replace("mysql+pymysql://", "mysql+aiomysql://")
            
            self._engine = create_async_engine(
                url,
                poolclass=QueuePool,
                pool_size=settings.DATABASE_POOL_SIZE,
                max_overflow=settings.DATABASE_MAX_OVERFLOW,
                pool_timeout=settings.DATABASE_POOL_TIMEOUT,
                pool_recycle=settings.DATABASE_POOL_RECYCLE,
                pool_pre_ping=True,
                echo=False
            )
        
        return self._engine
    
    async def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> list:
        """Execute a query and return results"""
        engine = await self.get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(query, params or {})
            return result.fetchall()
    
    async def close(self):
        """Close database connection"""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
    
    @asynccontextmanager
    async def get_session(self):
        """Get async database session"""
        engine = await self.get_engine()
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()


class DatabaseConnectionPool:
    """Manage multiple database connections"""
    
    def __init__(self):
        self.connections: Dict[str, DatabaseConnection] = {}
    
    def get_connection(self, connection_id: str, connection_url: str, database: Optional[str] = None) -> DatabaseConnection:
        """Get or create a database connection"""
        key = f"{connection_id}:{database or 'default'}"
        if key not in self.connections:
            self.connections[key] = DatabaseConnection(connection_url, database)
        return self.connections[key]
    
    async def close_all(self):
        """Close all connections"""
        for conn in self.connections.values():
            await conn.close()
        self.connections.clear()


# Global connection pool
connection_pool = DatabaseConnectionPool()
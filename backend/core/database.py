from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy.exc import OperationalError, DisconnectionError
import aiomysql
from contextlib import asynccontextmanager
import asyncio
import logging

from .config import settings

logger = logging.getLogger(__name__)

# Schema discovery connection tracking for tunnel reuse
_schema_discovery_connections = {}  # connection_url -> DatabaseConnection
_connection_warming_enabled = True


class DatabaseConnection:
    """Async database connection manager with connection pooling"""
    
    def __init__(self, connection_url: str, database: Optional[str] = None, is_schema_discovery: bool = False):
        self.connection_url = connection_url
        self.database = database
        self.is_schema_discovery = is_schema_discovery
        self._engine: Optional[AsyncEngine] = None
        self._connection_warmed = False
        self._last_activity = None
    
    async def get_engine(self) -> AsyncEngine:
        """Get or create async engine with connection pooling"""
        if self._engine is None:
            # Parse connection URL and add database if specified
            url = self.connection_url
            if self.database:
                # Handle URL with query parameters
                if "?" in url:
                    base_url, params = url.split("?", 1)
                    # Remove existing database from URL if present
                    if base_url.endswith("/"):
                        base_url = base_url.rstrip("/")
                    url = f"{base_url}/{self.database}?{params}"
                else:
                    # Remove trailing slash if present, then add database
                    if url.endswith("/"):
                        url = url.rstrip("/")
                    url = f"{url}/{self.database}"
            
            # Replace mysql+pymysql with mysql+aiomysql for async
            url = url.replace("mysql+pymysql://", "mysql+aiomysql://")
            
            # Clean up any URL parameters that are incompatible with aiomysql
            if "?" in url:
                base_url, params = url.split("?", 1)
                # Remove read_timeout and write_timeout parameters if they exist
                param_list = []
                for param in params.split("&"):
                    if not param.startswith(("read_timeout=", "write_timeout=")):
                        param_list.append(param)
                if param_list:
                    url = f"{base_url}?{'&'.join(param_list)}"
                else:
                    url = base_url
            
            # Check if this is a tunnel connection (localhost/127.0.0.1/ssh-proxy)
            is_tunnel = "127.0.0.1" in url or "localhost" in url or "schema-diff-ssh-proxy" in url
            
            # Adjust settings for SSH tunnel connections
            if is_tunnel:
                # Ultra-conservative settings for SSH tunnels with high latency
                pool_size = 1  # Single persistent connection for SSH tunnels
                pool_recycle = 1800  # 30 minutes - longer for stability
                pool_timeout = 300   # 5 minutes timeout for tunnel establishment
                max_overflow = 0  # No overflow - use single connection
            else:
                pool_size = settings.DATABASE_POOL_SIZE
                pool_recycle = settings.DATABASE_POOL_RECYCLE
                pool_timeout = settings.DATABASE_POOL_TIMEOUT
                max_overflow = settings.DATABASE_MAX_OVERFLOW
            
            self._engine = create_async_engine(
                url,
                poolclass=QueuePool,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_timeout=pool_timeout,
                pool_recycle=pool_recycle,
                pool_pre_ping=True,
                echo=False,
                # Additional MySQL-specific settings for stability  
                connect_args={
                    "charset": "utf8mb4",
                    "autocommit": True if is_tunnel else False,  # Auto-commit for SSH tunnel stability
                    "connect_timeout": 60 if is_tunnel else 30,  # Connection timeout
                    # SSH tunnel specific optimizations for Aurora
                    "init_command": (
                        "SET SESSION wait_timeout=600, "          # 10 minutes
                        "interactive_timeout=600, "              # 10 minutes  
                        "net_read_timeout=60, "                  # 1 minute
                        "net_write_timeout=60"                   # 1 minute
                        if is_tunnel else None
                    ),
                }
            )
        
        return self._engine
    
    async def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None, timeout: Optional[int] = None) -> list:
        """Execute a query with optimized connection retry logic for SSH tunnels"""
        # Determine if this is a tunnel connection for retry strategy
        is_tunnel = "127.0.0.1" in self.connection_url or "localhost" in self.connection_url or "schema-diff-ssh-proxy" in self.connection_url
        
        # Enhanced retry strategy for schema discovery operations
        if self.is_schema_discovery:
            max_retries = 5 if is_tunnel else 3  # More retries for schema discovery
            base_delay = 2 if is_tunnel else 1   # Longer delays for SSH tunnel stability
            query_timeout = timeout or (600 if is_tunnel else 30)  # 10 minutes for tunnel schema discovery
        else:
            max_retries = 3 if is_tunnel else 2  # Standard retries
            base_delay = 1 if is_tunnel else 0.5  # Standard delays
            query_timeout = timeout or (120 if is_tunnel else 30)  # 2 minutes for tunnel queries
        
        last_error = None
        
        for attempt in range(max_retries):
            try:
                engine = await self.get_engine()
                
                # Use asyncio.wait_for to implement query timeout
                async def execute_with_timeout():
                    from sqlalchemy import text
                    async with engine.connect() as conn:
                        # Convert string query to SQLAlchemy text object for aiomysql compatibility
                        sql_query = text(query) if isinstance(query, str) else query
                        result = await conn.execute(sql_query, params or {})
                        return result.fetchall()
                
                result = await asyncio.wait_for(execute_with_timeout(), timeout=query_timeout)
                
                # Update activity for schema discovery connections
                if self.is_schema_discovery:
                    self._last_activity = asyncio.get_event_loop().time()
                
                return result
                    
            except asyncio.TimeoutError as e:
                last_error = f"Query timeout after {query_timeout}s"
                logger.warning(f"Database query timeout (attempt {attempt + 1}/{max_retries}): {last_error}")
                
                if attempt < max_retries - 1:
                    # For timeout errors, reset connection and retry with longer timeout
                    if self._engine:
                        await self._engine.dispose()
                        self._engine = None
                    
                    # Increase timeout for subsequent attempts
                    query_timeout = int(query_timeout * 1.5)
                    
                    delay = base_delay * (2 ** attempt) + (attempt * 0.5)
                    logger.info(f"Retrying with increased timeout ({query_timeout}s) in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"Database query failed after {attempt + 1} timeout attempts")
                    raise OperationalError(last_error, None, None)
                    
            except (OperationalError, DisconnectionError) as e:
                last_error = str(e)
                error_msg = last_error.lower()
                is_connection_error = any(keyword in error_msg for keyword in [
                    "lost connection", "connection", "timeout", "can't connect",
                    "mysql server has gone away", "broken pipe", "connection reset",
                    "connection refused", "host is unreachable", "network is unreachable"
                ])
                
                if is_connection_error and attempt < max_retries - 1:
                    # Enhanced backoff strategy for tunnels
                    if is_tunnel:
                        # Progressive delay for tunnel stability
                        delay = base_delay * (2 ** attempt) + (attempt * 1.0)
                        # Cap maximum delay at 30 seconds for tunnels
                        delay = min(delay, 30)
                    else:
                        # Standard exponential backoff
                        delay = base_delay * (2 ** attempt) + (attempt * 0.5)
                    
                    logger.warning(
                        f"Database connection failed (attempt {attempt + 1}/{max_retries}): {last_error}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    
                    # Reset engine to force new connection
                    if self._engine:
                        await self._engine.dispose()
                        self._engine = None
                    
                    await asyncio.sleep(delay)
                    continue
                else:
                    # Non-retryable error or max retries exceeded
                    logger.error(f"Database query failed after {attempt + 1} attempts: {last_error}")
                    raise
                    
            except Exception as e:
                # Non-connection errors - don't retry
                last_error = str(e)
                logger.error(f"Database query failed with non-connection error: {last_error}")
                raise
    
    async def close(self):
        """Close database connection"""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
    
    async def execute_ddl(self, statement: str) -> bool:
        """Execute a DDL statement (CREATE, DROP, ALTER, etc.) that doesn't return rows"""
        try:
            engine = await self.get_engine()
            from sqlalchemy import text
            
            async with engine.connect() as conn:
                sql_stmt = text(statement) if isinstance(statement, str) else statement
                await conn.execute(sql_stmt)
                await conn.commit()
            
            return True
        except Exception as e:
            logger.error(f"DDL execution failed: {e}")
            raise
    
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
    
    async def warm_connection(self) -> bool:
        """Pre-warm database connection for schema discovery operations"""
        try:
            # Test basic connectivity
            await self.execute_query("SELECT 1")
            self._connection_warmed = True
            self._last_activity = asyncio.get_event_loop().time()
            logger.info(f"Database connection warmed successfully: {self.connection_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to warm database connection: {e}")
            return False
    
    async def keep_alive_ping(self) -> bool:
        """Send keep-alive ping to maintain connection"""
        try:
            await self.execute_query("SELECT 1")
            self._last_activity = asyncio.get_event_loop().time()
            return True
        except Exception as e:
            logger.debug(f"Keep-alive ping failed: {e}")
            return False
    
    def is_connection_stale(self, max_idle_seconds: int = 1800) -> bool:
        """Check if connection has been idle for too long (default: 30 minutes)"""
        if not self._last_activity:
            return False
        
        current_time = asyncio.get_event_loop().time()
        idle_time = current_time - self._last_activity
        return idle_time > max_idle_seconds
    
    async def execute_query_with_keep_alive(self, query: str, params: Optional[Dict[str, Any]] = None) -> list:
        """Execute query with automatic keep-alive tracking for schema discovery"""
        result = await self.execute_query(query, params)
        
        # Update activity timestamp for schema discovery connections
        if self.is_schema_discovery:
            self._last_activity = asyncio.get_event_loop().time()
        
        return result


class DatabaseConnectionPool:
    """Manage multiple database connections"""
    
    def __init__(self):
        self.connections: Dict[str, DatabaseConnection] = {}
    
    def get_connection(self, connection_id: str, connection_url: str, database: Optional[str] = None, is_schema_discovery: bool = False) -> DatabaseConnection:
        """Get or create a database connection"""
        key = f"{connection_id}:{database or 'default'}"
        if key not in self.connections:
            self.connections[key] = DatabaseConnection(connection_url, database, is_schema_discovery=is_schema_discovery)
        return self.connections[key]
    
    def get_schema_discovery_connection(self, connection_id: str, connection_url: str, database: Optional[str] = None) -> DatabaseConnection:
        """Get or create a schema discovery optimized connection"""
        return self.get_connection(connection_id, connection_url, database, is_schema_discovery=True)
    
    async def close_all(self):
        """Close all connections"""
        for conn in self.connections.values():
            await conn.close()
        self.connections.clear()


# Global functions for schema discovery connection management
async def get_schema_discovery_connection(connection_id: str, connection_url: str, database: Optional[str] = None) -> DatabaseConnection:
    """Get or create a schema discovery optimized database connection"""
    conn = connection_pool.get_schema_discovery_connection(connection_id, connection_url, database)
    
    # Track for reuse
    global _schema_discovery_connections
    connection_key = f"{connection_url}:{database or 'default'}"
    _schema_discovery_connections[connection_key] = conn
    
    return conn

async def warm_schema_discovery_connections(connections: List[tuple]) -> Dict[str, bool]:
    """Warm multiple schema discovery connections"""
    results = {}
    
    for connection_id, connection_url, database in connections:
        try:
            conn = await get_schema_discovery_connection(connection_id, connection_url, database)
            success = await conn.warm_connection()
            results[f"{connection_url}:{database or 'default'}"] = success
            logger.info(f"Connection warming {'succeeded' if success else 'failed'}: {connection_id}")
        except Exception as e:
            logger.error(f"Failed to warm connection {connection_id}: {e}")
            results[f"{connection_url}:{database or 'default'}"] = False
    
    return results

async def maintain_schema_discovery_connections():
    """Periodic maintenance for schema discovery connections"""
    global _schema_discovery_connections
    
    stale_connections = []
    for connection_key, conn in _schema_discovery_connections.items():
        if conn.is_connection_stale():
            logger.info(f"Refreshing stale schema discovery connection: {connection_key}")
            try:
                # Try to refresh with a keep-alive ping
                ping_success = await conn.keep_alive_ping()
                if not ping_success:
                    stale_connections.append(connection_key)
                    logger.warning(f"Connection refresh failed: {connection_key}")
            except Exception as e:
                logger.error(f"Connection maintenance failed for {connection_key}: {e}")
                stale_connections.append(connection_key)
    
    # Remove stale connections
    for connection_key in stale_connections:
        try:
            await _schema_discovery_connections[connection_key].close()
            del _schema_discovery_connections[connection_key]
            logger.info(f"Removed stale connection: {connection_key}")
        except Exception as e:
            logger.error(f"Failed to close stale connection {connection_key}: {e}")

# Global connection pool
connection_pool = DatabaseConnectionPool()
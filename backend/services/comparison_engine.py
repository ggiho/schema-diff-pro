import asyncio
import uuid
from typing import List, Dict, Any, AsyncGenerator
from datetime import datetime
import logging
import time
from sqlalchemy.exc import OperationalError

from models.base import (
    ComparisonResult, ComparisonProgress, ComparisonOptions,
    DatabaseConfig, Difference, ObjectType
)
from core.database import DatabaseConnection, connection_pool
from services.comparers.table_comparer import TableComparer
from services.comparers.index_comparer import IndexComparer
from services.comparers.constraint_comparer import ConstraintComparer
from services.ssh_tunnel_manager import tunnel_manager

logger = logging.getLogger(__name__)


class ComparisonEngine:
    """Main engine that orchestrates database comparison"""
    
    def __init__(self):
        self.comparers = {
            ObjectType.TABLE: TableComparer,
            ObjectType.INDEX: IndexComparer,
            ObjectType.CONSTRAINT: ConstraintComparer,
        }
        self.max_retries = 3
        self.retry_delay = 2  # seconds
    
    async def _setup_ssh_tunnel_if_needed(self, config: DatabaseConfig, connection_name: str) -> DatabaseConfig:
        """Setup SSH tunnel if configured and update connection URL"""
        # Check if config has SSH tunnel and import the SSH-aware config model
        if hasattr(config, 'ssh_tunnel') and config.ssh_tunnel and config.ssh_tunnel.enabled:
            logger.info(f"Setting up SSH tunnel for {connection_name} to {config.ssh_tunnel.ssh_host}:{config.ssh_tunnel.ssh_port}")
            
            try:
                # CRITICAL FIX: Update SSH tunnel to use actual database host as remote target
                # SSH tunnel should forward: local_port -> jump_host -> actual_database_host:port
                config.ssh_tunnel.remote_bind_host = config.host  # Use actual Aurora DB host
                config.ssh_tunnel.remote_bind_port = config.port  # Use actual Aurora DB port
                
                logger.info(f"SSH tunnel will forward to: {config.ssh_tunnel.remote_bind_host}:{config.ssh_tunnel.remote_bind_port}")
                
                # Create connection key for tunnel reuse
                connection_key = f"{config.ssh_tunnel.ssh_host}:{config.ssh_tunnel.ssh_port}:{config.ssh_tunnel.remote_bind_host}:{config.ssh_tunnel.remote_bind_port}"
                
                # Get or create tunnel for schema discovery
                tunnel_info = await tunnel_manager.get_or_create_tunnel_for_schema_discovery(
                    config.ssh_tunnel,
                    connection_key,
                    timeout=120  # Extended timeout for comparison operations
                )
                
                # Enhanced status checking
                if not tunnel_info or tunnel_info.status.value != "connected":
                    error_msg = tunnel_info.last_error if tunnel_info else "Unknown tunnel error"
                    logger.error(f"SSH tunnel connection failed for {connection_name}: {error_msg}")
                    raise Exception(f"SSH tunnel failed for {connection_name}: {error_msg}")
                
                if not tunnel_info.local_port:
                    raise Exception(f"SSH tunnel established but no local port assigned for {connection_name}")
                
                logger.info(f"SSH tunnel established for {connection_name}: {tunnel_info.tunnel_id} -> local port {tunnel_info.local_port}")
                
                # Create new config with tunnel settings - CRITICAL FIX
                from models.ssh_tunnel import DatabaseConfigWithSSH
                import os
                
                # In Docker environment, use schema-diff-ssh-proxy hostname, otherwise localhost
                tunnel_host = "schema-diff-ssh-proxy" if os.getenv('DOCKER_ENV') == 'true' else "127.0.0.1"
                
                updated_config = DatabaseConfigWithSSH(
                    host=tunnel_host,  # FIXED: Use proper tunnel host
                    port=tunnel_info.local_port,  # FIXED: Use tunnel port
                    user=config.user,
                    password=config.password,
                    database=config.database,
                    ssh_tunnel=config.ssh_tunnel
                )
                
                # Update the SSH tunnel config with the actual local port
                updated_config.ssh_tunnel.local_bind_port = tunnel_info.local_port
                
                # Verify the updated connection URL
                updated_url = updated_config.get_connection_url()
                logger.info(f"Updated {connection_name} connection URL (TUNNEL): {updated_url.split('@')[1] if '@' in updated_url else updated_url}")
                
                return updated_config
                
            except Exception as e:
                logger.error(f"Failed to setup SSH tunnel for {connection_name}: {e}")
                raise Exception(f"SSH tunnel setup failed for {connection_name}: {e}")
        
        logger.debug(f"No SSH tunnel required for {connection_name}")
        return config
    
    async def _execute_with_retry(self, operation, operation_name: str):
        """Execute operation with retry logic for database connection issues"""
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                return await operation()
            except (OperationalError, Exception) as e:
                last_exception = e
                error_str = str(e).lower()
                
                # Check if this is a connection-related error that we should retry
                connection_errors = [
                    'lost connection to mysql server',
                    'mysql server has gone away',
                    'connection timeout',
                    'broken pipe',
                    'connection refused'
                ]
                
                is_connection_error = any(error in error_str for error in connection_errors)
                
                if is_connection_error and attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"{operation_name} failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # Either not a connection error or final attempt
                    logger.error(f"{operation_name} failed after {attempt + 1} attempts: {e}")
                    raise
        
        # This should never be reached, but just in case
        raise last_exception
    
    async def compare_databases(
        self,
        source_config: DatabaseConfig,
        target_config: DatabaseConfig,
        options: ComparisonOptions
    ) -> AsyncGenerator[ComparisonProgress, ComparisonResult]:
        """Compare two databases with progress updates"""
        comparison_id = str(uuid.uuid4())
        started_at = datetime.now()
        all_differences: List[Difference] = []
        
        # Setup SSH tunnels if needed
        logger.info(f"Comparison {comparison_id}: Setting up connections")
        
        # Show tunnel setup progress
        tunnel_count = 0
        if hasattr(source_config, 'ssh_tunnel') and source_config.ssh_tunnel and source_config.ssh_tunnel.enabled:
            tunnel_count += 1
        if hasattr(target_config, 'ssh_tunnel') and target_config.ssh_tunnel and target_config.ssh_tunnel.enabled:
            tunnel_count += 1
            
        if tunnel_count > 0:
            yield ComparisonProgress(
                comparison_id=comparison_id,
                phase="discovery",
                current=0,
                total=tunnel_count,
                message=f"Establishing SSH tunnels ({tunnel_count} required)"
            )
        
        try:
            source_config = await self._setup_ssh_tunnel_if_needed(source_config, "source")
            target_config = await self._setup_ssh_tunnel_if_needed(target_config, "target")
        except Exception as e:
            # SSH tunnel setup failed - provide clear error message
            error_msg = f"SSH tunnel setup failed: {str(e)}"
            logger.error(f"Comparison {comparison_id}: {error_msg}")
            
            yield ComparisonProgress(
                comparison_id=comparison_id,
                phase="error",
                current=0,
                total=1,
                message=f"CRITICAL: {error_msg}"
            )
            
            # Return early result with SSH tunnel error
            completed_at = datetime.now()
            duration = (completed_at - started_at).total_seconds()
            
            yield ComparisonResult(
                comparison_id=comparison_id,
                started_at=started_at,
                completed_at=completed_at,
                source_config=source_config,
                target_config=target_config,
                options=options,
                differences=[],
                summary={"error": error_msg, "ssh_tunnel_error": True},
                duration_seconds=duration,
                objects_compared=0,
                errors=[error_msg]
            )
            return
        
        if tunnel_count > 0:
            yield ComparisonProgress(
                comparison_id=comparison_id,
                phase="discovery",
                current=tunnel_count,
                total=tunnel_count,
                message="SSH tunnels established successfully"
            )
        
        # Create connections with updated configs (including tunnel ports)
        # Use empty string for URL to avoid duplication, database will be passed separately
        source_url = source_config.get_connection_url(database="")
        target_url = target_config.get_connection_url(database="")
        
        logger.info(f"Comparison {comparison_id}: Source connection URL: {source_url.split('@')[1] if '@' in source_url else source_url}")
        logger.info(f"Comparison {comparison_id}: Source database: {source_config.database}")
        logger.info(f"Comparison {comparison_id}: Target connection URL: {target_url.split('@')[1] if '@' in target_url else target_url}")
        logger.info(f"Comparison {comparison_id}: Target database: {target_config.database}")
        
        # Use database only if user provided specific schema, otherwise use empty/default
        source_database = source_config.database if source_config.database and source_config.database.strip() else None
        target_database = target_config.database if target_config.database and target_config.database.strip() else None
        
        source_conn = connection_pool.get_schema_discovery_connection(
            f"source_{comparison_id}",
            source_url,
            source_database
        )
        target_conn = connection_pool.get_schema_discovery_connection(
            f"target_{comparison_id}",
            target_url,
            target_database
        )
        
        try:
            # CRITICAL: Test database connections early and fail fast
            yield ComparisonProgress(
                comparison_id=comparison_id,
                phase="discovery",
                current=0,
                total=2,
                message="Testing database connections"
            )
            
            # Test source connection first
            try:
                logger.info(f"Testing source database connection...")
                await source_conn.execute_query("SELECT 1 as test", timeout=15)
                logger.info(f"✅ Source database connection successful")
                
                yield ComparisonProgress(
                    comparison_id=comparison_id,
                    phase="discovery", 
                    current=1,
                    total=2,
                    message="Source connection OK, testing target connection"
                )
                
            except Exception as e:
                error_msg = f"Source database connection failed: {str(e)}"
                logger.error(f"❌ {error_msg}")
                
                yield ComparisonProgress(
                    comparison_id=comparison_id,
                    phase="error",
                    current=0,
                    total=1,
                    message=f"FAILED: Source database unreachable - {str(e)}"
                )
                
                # Return early with source connection error
                completed_at = datetime.now()
                duration = (completed_at - started_at).total_seconds()
                
                yield ComparisonResult(
                    comparison_id=comparison_id,
                    started_at=started_at,
                    completed_at=completed_at,
                    source_config=source_config,
                    target_config=target_config,
                    options=options,
                    differences=[],
                    summary={"error": error_msg, "source_connection_failed": True},
                    duration_seconds=duration,
                    objects_compared=0,
                    errors=[error_msg]
                )
                return
            
            # Test target connection  
            try:
                logger.info(f"Testing target database connection...")
                await target_conn.execute_query("SELECT 1 as test", timeout=15)
                logger.info(f"✅ Target database connection successful")
                
                yield ComparisonProgress(
                    comparison_id=comparison_id,
                    phase="discovery",
                    current=2, 
                    total=2,
                    message="Both database connections verified"
                )
                
            except Exception as e:
                error_msg = f"Target database connection failed: {str(e)}"
                logger.error(f"❌ {error_msg}")
                
                yield ComparisonProgress(
                    comparison_id=comparison_id,
                    phase="error",
                    current=0,
                    total=1,
                    message=f"FAILED: Target database unreachable - {str(e)}"
                )
                
                # Return early with target connection error
                completed_at = datetime.now()
                duration = (completed_at - started_at).total_seconds()
                
                yield ComparisonResult(
                    comparison_id=comparison_id,
                    started_at=started_at,
                    completed_at=completed_at,
                    source_config=source_config,
                    target_config=target_config,
                    options=options,
                    differences=[],
                    summary={"error": error_msg, "target_connection_failed": True},
                    duration_seconds=duration,
                    objects_compared=0,
                    errors=[error_msg]
                )
                return
                    
            # Determine which comparers to run
            active_comparers = []
            if options.compare_tables and options.compare_columns:
                active_comparers.append((ObjectType.TABLE, TableComparer))
            if options.compare_indexes:
                active_comparers.append((ObjectType.INDEX, IndexComparer))
            if options.compare_constraints:
                active_comparers.append((ObjectType.CONSTRAINT, ConstraintComparer))
            
            total_phases = len(active_comparers)
            current_phase = 0
            
            # Run each comparer with retry logic
            for object_type, comparer_class in active_comparers:
                current_phase += 1
                
                yield ComparisonProgress(
                    comparison_id=comparison_id,
                    phase="comparison",
                    current=current_phase,
                    total=total_phases,
                    message=f"Comparing {object_type.value}s"
                )
                
                # Execute comparer with retry mechanism
                async def run_comparer():
                    comparer = comparer_class(
                        source_conn,
                        target_conn,
                        options,
                        comparison_id
                    )
                    
                    # Collect progress and differences
                    progress_list = []
                    async for progress in comparer.compare():
                        progress_list.append(progress)
                    
                    return comparer, progress_list
                
                try:
                    comparer, progress_list = await self._execute_with_retry(
                        run_comparer,
                        f"Comparing {object_type.value}s"
                    )
                    
                    # Yield collected progress
                    for progress in progress_list:
                        yield progress
                    
                    all_differences.extend(comparer.differences)
                    
                except Exception as e:
                    error_msg = str(e)
                    
                    # Check if this is a data discovery failure that should stop the comparison
                    if ("Failed to discover any table data" in error_msg or 
                        "Both chunked and fallback discovery failed" in error_msg or
                        "Database may be unreachable" in error_msg):
                        
                        # Critical failure - stop the entire comparison
                        yield ComparisonProgress(
                            comparison_id=comparison_id,
                            phase="error",
                            current=current_phase,
                            total=total_phases,
                            message=f"CRITICAL: Database connection failed. {error_msg}"
                        )
                        logger.error(f"Stopping comparison due to critical database connection failure: {e}")
                        
                        # Return early result with error
                        completed_at = datetime.now()
                        duration = (completed_at - started_at).total_seconds()
                        
                        yield ComparisonResult(
                            comparison_id=comparison_id,
                            started_at=started_at,
                            completed_at=completed_at,
                            source_config=source_config,
                            target_config=target_config,
                            options=options,
                            differences=[],
                            summary={"error": error_msg, "total_objects_compared": 0},
                            duration_seconds=duration,
                            objects_compared=0
                        )
                        return
                    
                    # Non-critical error - continue with next comparer but log the error
                    yield ComparisonProgress(
                        comparison_id=comparison_id,
                        phase="comparison",
                        current=current_phase,
                        total=total_phases,
                        message=f"WARNING: Failed to compare {object_type.value}s: {error_msg}"
                    )
                    logger.error(f"Comparer {object_type.value} failed: {e}")
                    # Continue with next comparer
            
            # Analysis phase
            yield ComparisonProgress(
                comparison_id=comparison_id,
                phase="analysis",
                current=1,
                total=1,
                message="Analyzing differences and generating summary"
            )
            
            summary = self._generate_summary(all_differences)
            
            # Sort differences by fix order and severity
            all_differences.sort(
                key=lambda d: (d.fix_order, d.severity.value, d.object_name)
            )
            
            completed_at = datetime.now()
            duration = (completed_at - started_at).total_seconds()
            
            # Final report phase
            yield ComparisonProgress(
                comparison_id=comparison_id,
                phase="report",
                current=1,
                total=1,
                message=f"Comparison complete. Found {len(all_differences)} differences"
            )
            
            # Yield final result
            result = ComparisonResult(
                comparison_id=comparison_id,
                started_at=started_at,
                completed_at=completed_at,
                source_config=source_config,
                target_config=target_config,
                options=options,
                differences=all_differences,
                summary=summary,
                duration_seconds=duration,
                objects_compared=summary.get("total_objects_compared", 0)
            )
            
            yield result
            
        except Exception as e:
            logger.error(f"Comparison failed: {str(e)}")
            raise
        finally:
            # Clean up connections
            await source_conn.close()
            await target_conn.close()
    
    def _generate_summary(self, differences: List[Difference]) -> Dict[str, Any]:
        """Generate summary statistics from differences"""
        summary = {
            "total_differences": len(differences),
            "by_severity": {},
            "by_type": {},
            "by_object_type": {},
            "critical_count": 0,
            "can_auto_fix": 0,
            "data_loss_risks": [],
            "schemas_affected": set(),
            "tables_affected": set()
        }
        
        for diff in differences:
            # Count by severity
            severity = diff.severity.value
            summary["by_severity"][severity] = summary["by_severity"].get(severity, 0) + 1
            
            # Count by difference type
            diff_type = diff.diff_type.value
            summary["by_type"][diff_type] = summary["by_type"].get(diff_type, 0) + 1
            
            # Count by object type
            obj_type = diff.object_type.value
            summary["by_object_type"][obj_type] = summary["by_object_type"].get(obj_type, 0) + 1
            
            # Track critical issues
            if diff.severity == "critical":
                summary["critical_count"] += 1
            
            # Track auto-fixable
            if diff.can_auto_fix:
                summary["can_auto_fix"] += 1
            
            # Track data loss risks
            if any(warning for warning in diff.warnings if "data loss" in warning.lower()):
                summary["data_loss_risks"].append({
                    "object": f"{diff.schema_name}.{diff.object_name}",
                    "type": diff.diff_type.value,
                    "description": diff.description
                })
            
            # Track affected schemas and tables
            if diff.schema_name:
                summary["schemas_affected"].add(diff.schema_name)
            if diff.object_name and diff.object_type in [ObjectType.TABLE, ObjectType.COLUMN]:
                table_name = f"{diff.schema_name}.{diff.object_name}" if diff.schema_name else diff.object_name
                summary["tables_affected"].add(table_name)
        
        # Convert sets to lists for JSON serialization
        summary["schemas_affected"] = list(summary["schemas_affected"])
        summary["tables_affected"] = list(summary["tables_affected"])
        summary["total_objects_compared"] = len(summary["tables_affected"]) * 3  # Rough estimate
        
        return summary
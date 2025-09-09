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
        
        # Create connections
        source_conn = connection_pool.get_connection(
            f"source_{comparison_id}",
            source_config.get_connection_url()
        )
        target_conn = connection_pool.get_connection(
            f"target_{comparison_id}",
            target_config.get_connection_url()
        )
        
        try:
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
                    # If all retries failed, yield error progress and continue with next comparer
                    yield ComparisonProgress(
                        comparison_id=comparison_id,
                        phase="comparison",  # Use valid phase, indicate error in message
                        current=current_phase,
                        total=total_phases,
                        message=f"ERROR: Failed to compare {object_type.value}s after retries: {str(e)}"
                    )
                    logger.error(f"Comparer {object_type.value} failed completely: {e}")
                    # Continue with next comparer instead of failing the entire comparison
            
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
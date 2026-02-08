from typing import Dict, Any, List, AsyncGenerator, Set, Tuple
import logging
from sqlalchemy import text

from .base_comparer import BaseComparer
from models.base import (
    Difference, ObjectType, DiffType, SeverityLevel, ComparisonProgress
)
from core.database import DatabaseConnection
from core.config import settings

logger = logging.getLogger(__name__)


class IndexComparer(BaseComparer):
    """Compare database indexes"""
    
    object_type = ObjectType.INDEX
    
    async def discover_objects(self, connection: DatabaseConnection) -> Dict[str, Any]:
        """Discover all indexes"""
        query = text("""
        SELECT 
            s.TABLE_SCHEMA,
            s.TABLE_NAME,
            s.INDEX_NAME,
            s.NON_UNIQUE,
            s.INDEX_TYPE,
            GROUP_CONCAT(
                s.COLUMN_NAME 
                ORDER BY s.SEQ_IN_INDEX
                SEPARATOR ','
            ) as COLUMNS,
            GROUP_CONCAT(
                CONCAT(s.COLUMN_NAME, '(', IFNULL(s.SUB_PART, ''), ')')
                ORDER BY s.SEQ_IN_INDEX
                SEPARATOR ','
            ) as COLUMN_DETAILS,
            MAX(s.NULLABLE) as HAS_NULLABLE,
            MAX(s.COMMENT) as INDEX_COMMENT
        FROM information_schema.STATISTICS s
        WHERE s.TABLE_SCHEMA NOT IN :system_dbs
        GROUP BY s.TABLE_SCHEMA, s.TABLE_NAME, s.INDEX_NAME, s.NON_UNIQUE, s.INDEX_TYPE
        ORDER BY s.TABLE_SCHEMA, s.TABLE_NAME, s.INDEX_NAME
        """)
        
        results = await connection.execute_query(
            query,
            {"system_dbs": tuple(settings.SYSTEM_DATABASES)}
        )
        
        indexes = {}
        for row in results:
            schema_name = row[0]
            table_name = row[1]
            index_name = row[2]
            
            # Skip if table is filtered out
            if not self.should_compare_object(schema_name, table_name):
                continue
            
            # Skip PRIMARY key indexes (these are handled by constraint comparer)
            if index_name == "PRIMARY":
                continue
            
            index_key = f"{schema_name}.{table_name}.{index_name}"
            
            indexes[index_key] = {
                "schema_name": schema_name,
                "table_name": table_name,
                "index_name": index_name,
                "is_unique": not row[3],  # NON_UNIQUE = 0 means unique
                "index_type": row[4],
                "columns": row[5],
                "column_details": row[6],
                "has_nullable": row[7] == "YES",
                "comment": row[8]
            }
        
        return indexes
    
    def _create_index_signature(self, index: Dict[str, Any]) -> str:
        """Create a signature for an index based on its columns and properties (not name)"""
        return f"{index['schema_name']}.{index['table_name']}|{index['columns']}|{index['is_unique']}|{index['index_type']}"
    
    def _create_table_key(self, index: Dict[str, Any]) -> str:
        """Create a table key for grouping indexes"""
        return f"{index['schema_name']}.{index['table_name']}"

    def create_missing_difference(
        self,
        obj_name: str,
        obj_data: Any,
        missing_in: str
    ) -> Difference:
        """Override to handle severity based on index uniqueness"""
        diff = super().create_missing_difference(obj_name, obj_data, missing_in)

        # Adjust severity based on uniqueness
        # UNIQUE indexes: HIGH (data integrity)
        # Non-unique indexes: MEDIUM (just performance)
        is_unique = obj_data.get("is_unique", False)
        if not is_unique:
            diff.severity = SeverityLevel.MEDIUM
        else:
            diff.severity = SeverityLevel.HIGH

        return diff

    async def compare(self) -> AsyncGenerator[ComparisonProgress, None]:
        """Override compare to detect renamed indexes"""
        # Discovery phase
        yield ComparisonProgress(
            comparison_id=self.comparison_id,
            phase="discovery",
            current=0,
            total=2,
            current_object=f"Discovering {self.object_type.value}s in source",
            message=f"Starting {self.object_type.value} discovery"
        )
        
        import asyncio
        source_task = asyncio.create_task(self.discover_objects(self.source_conn))
        target_task = asyncio.create_task(self.discover_objects(self.target_conn))
        
        yield ComparisonProgress(
            comparison_id=self.comparison_id,
            phase="discovery",
            current=1,
            total=2,
            current_object=f"Discovering {self.object_type.value}s in both databases"
        )
        
        source_objects = await source_task
        target_objects = await target_task
        
        yield ComparisonProgress(
            comparison_id=self.comparison_id,
            phase="discovery",
            current=2,
            total=2,
            message=f"Discovery complete. Found {len(source_objects)} source and {len(target_objects)} target {self.object_type.value}s"
        )
        
        # Track processed indexes to avoid duplicates
        processed_source: Set[str] = set()
        processed_target: Set[str] = set()
        renamed_pairs: List[Tuple[Dict, Dict]] = []
        duplicate_source: List[Tuple[Dict, Dict]] = []  # (duplicate_idx, original_idx)
        duplicate_target: List[Tuple[Dict, Dict]] = []  # (duplicate_idx, original_idx)
        
        # Build signature-based lookup (list to handle duplicates)
        source_by_signature: Dict[str, List[Dict[str, Any]]] = {}
        target_by_signature: Dict[str, List[Dict[str, Any]]] = {}
        
        for key, idx in source_objects.items():
            sig = self._create_index_signature(idx)
            if sig not in source_by_signature:
                source_by_signature[sig] = []
            source_by_signature[sig].append(idx)
        
        for key, idx in target_objects.items():
            sig = self._create_index_signature(idx)
            if sig not in target_by_signature:
                target_by_signature[sig] = []
            target_by_signature[sig].append(idx)
        
        # Step 1: Exact name match FIRST (highest priority)
        for obj_name in source_objects.keys():
            if obj_name in target_objects:
                processed_source.add(obj_name)
                processed_target.add(obj_name)
        
        # Step 2: Detect duplicate indexes within same database (only for remaining indexes)
        for sig, idx_list in source_by_signature.items():
            # Filter to only unprocessed indexes
            remaining = [idx for idx in idx_list 
                if f"{idx['schema_name']}.{idx['table_name']}.{idx['index_name']}" not in processed_source]
            if len(remaining) > 1:
                # First one is the "original", rest are duplicates
                original = remaining[0]
                for dup in remaining[1:]:
                    duplicate_source.append((dup, original))
                    dup_key = f"{dup['schema_name']}.{dup['table_name']}.{dup['index_name']}"
                    processed_source.add(dup_key)
                    logger.info(f"Duplicate in source: {dup['index_name']} (same as {original['index_name']})")
        
        for sig, idx_list in target_by_signature.items():
            # Filter to only unprocessed indexes
            remaining = [idx for idx in idx_list 
                if f"{idx['schema_name']}.{idx['table_name']}.{idx['index_name']}" not in processed_target]
            if len(remaining) > 1:
                # First one is the "original", rest are duplicates
                original = remaining[0]
                for dup in remaining[1:]:
                    duplicate_target.append((dup, original))
                    dup_key = f"{dup['schema_name']}.{dup['table_name']}.{dup['index_name']}"
                    processed_target.add(dup_key)
                    logger.info(f"Duplicate in target: {dup['index_name']} (same as {original['index_name']})")
        
        # Step 3: Signature-based rename detection for remaining indexes
        for sig, source_list in source_by_signature.items():
            if sig not in target_by_signature:
                continue
            
            target_list = target_by_signature[sig]
            
            # Filter out already processed
            remaining_source = [idx for idx in source_list 
                if f"{idx['schema_name']}.{idx['table_name']}.{idx['index_name']}" not in processed_source]
            remaining_target = [idx for idx in target_list 
                if f"{idx['schema_name']}.{idx['table_name']}.{idx['index_name']}" not in processed_target]
            
            # Match remaining indexes 1:1 as renames
            for i, source_idx in enumerate(remaining_source):
                if i >= len(remaining_target):
                    break
                target_idx = remaining_target[i]
                
                source_key = f"{source_idx['schema_name']}.{source_idx['table_name']}.{source_idx['index_name']}"
                target_key = f"{target_idx['schema_name']}.{target_idx['table_name']}.{target_idx['index_name']}"
                
                logger.info(f"Rename detected: {source_idx['index_name']} -> {target_idx['index_name']}")
                renamed_pairs.append((source_idx, target_idx))
                processed_source.add(source_key)
                processed_target.add(target_key)
        
        # Comparison phase
        total_objects = len(set(list(source_objects.keys()) + list(target_objects.keys())))
        
        if total_objects > 0:
            current = 0
            
            # Process duplicate indexes in source
            for dup_idx, orig_idx in duplicate_source:
                current += 1
                yield ComparisonProgress(
                    comparison_id=self.comparison_id,
                    phase="comparison",
                    current=current,
                    total=total_objects,
                    current_object=f"{dup_idx['index_name']} (duplicate)",
                    message=f"Detected duplicate index in source"
                )
                
                self.differences.append(Difference(
                    diff_type=DiffType.INDEX_DUPLICATE_SOURCE,
                    severity=SeverityLevel.LOW,
                    object_type=ObjectType.INDEX,
                    schema_name=dup_idx['schema_name'],
                    object_name=dup_idx['table_name'],
                    sub_object_name=dup_idx['index_name'],
                    source_value=dup_idx,
                    target_value=orig_idx,
                    source_display_value=f"{dup_idx['index_name']} ({dup_idx['columns']})",
                    target_display_value=f"{orig_idx['index_name']} ({orig_idx['columns']})",
                    description=f"Duplicate index in source: '{dup_idx['index_name']}' has same structure as '{orig_idx['index_name']}'",
                    can_auto_fix=True,
                    fix_order=self.get_fix_order(),
                    warnings=["Consider removing one of the duplicate indexes"]
                ))
            
            # Process duplicate indexes in target
            for dup_idx, orig_idx in duplicate_target:
                current += 1
                yield ComparisonProgress(
                    comparison_id=self.comparison_id,
                    phase="comparison",
                    current=current,
                    total=total_objects,
                    current_object=f"{dup_idx['index_name']} (duplicate)",
                    message=f"Detected duplicate index in target"
                )
                
                self.differences.append(Difference(
                    diff_type=DiffType.INDEX_DUPLICATE_TARGET,
                    severity=SeverityLevel.LOW,
                    object_type=ObjectType.INDEX,
                    schema_name=dup_idx['schema_name'],
                    object_name=dup_idx['table_name'],
                    sub_object_name=dup_idx['index_name'],
                    source_value=orig_idx,
                    target_value=dup_idx,
                    source_display_value=f"{orig_idx['index_name']} ({orig_idx['columns']})",
                    target_display_value=f"{dup_idx['index_name']} ({dup_idx['columns']})",
                    description=f"Duplicate index in target: '{dup_idx['index_name']}' has same structure as '{orig_idx['index_name']}'",
                    can_auto_fix=True,
                    fix_order=self.get_fix_order(),
                    warnings=["Consider removing one of the duplicate indexes"]
                ))
            
            # Process renamed indexes
            for source_idx, target_idx in renamed_pairs:
                current += 1
                yield ComparisonProgress(
                    comparison_id=self.comparison_id,
                    phase="comparison",
                    current=current,
                    total=total_objects,
                    current_object=f"{source_idx['index_name']} → {target_idx['index_name']}",
                    message=f"Detected index rename"
                )
                
                self.differences.append(Difference(
                    diff_type=DiffType.INDEX_RENAMED,
                    severity=SeverityLevel.MEDIUM,  # Index rename can affect app code
                    object_type=ObjectType.INDEX,
                    schema_name=source_idx['schema_name'],
                    object_name=source_idx['table_name'],
                    sub_object_name=source_idx['index_name'],
                    source_value=source_idx,
                    target_value=target_idx,
                    source_display_value=source_idx['index_name'],
                    target_display_value=target_idx['index_name'],
                    description=f"Index renamed: {source_idx['index_name']} → {target_idx['index_name']}",
                    can_auto_fix=True,
                    fix_order=self.get_fix_order()
                ))
            
            # Process remaining indexes (missing or matched by name)
            for obj_name in set(list(source_objects.keys()) + list(target_objects.keys())):
                if obj_name in processed_source or obj_name in processed_target:
                    continue
                
                current += 1
                yield ComparisonProgress(
                    comparison_id=self.comparison_id,
                    phase="comparison",
                    current=current,
                    total=total_objects,
                    current_object=obj_name,
                    message=f"Comparing {self.object_type.value}: {obj_name}"
                )
                
                source_obj = source_objects.get(obj_name)
                target_obj = target_objects.get(obj_name)
                
                if source_obj and target_obj:
                    # Object exists in both - compare details
                    obj_differences = await self.compare_single_object(obj_name, source_obj, target_obj)
                    self.differences.extend(obj_differences)
                elif source_obj and not target_obj:
                    # Check if this might be a renamed index (already processed)
                    source_key = f"{source_obj['schema_name']}.{source_obj['table_name']}.{source_obj['index_name']}"
                    if source_key not in processed_source:
                        # Object only in source
                        self.differences.append(self.create_missing_difference(
                            obj_name, source_obj, "target"
                        ))
                elif not source_obj and target_obj:
                    target_key = f"{target_obj['schema_name']}.{target_obj['table_name']}.{target_obj['index_name']}"
                    if target_key not in processed_target:
                        # Object only in target
                        self.differences.append(self.create_missing_difference(
                            obj_name, target_obj, "source"
                        ))
    
    async def compare_objects(
        self,
        source_objects: Dict[str, Any],
        target_objects: Dict[str, Any]
    ) -> List[Difference]:
        """Compare discovered objects and return differences"""
        # This method is required by the abstract base class
        # The actual comparison logic is handled in the overridden compare() method
        return []
    
    async def compare_single_object(
        self,
        index_key: str,
        source_index: Dict[str, Any],
        target_index: Dict[str, Any]
    ) -> List[Difference]:
        """Compare a single index"""
        differences = []
        schema_name = source_index["schema_name"]
        table_name = source_index["table_name"]
        index_name = source_index["index_name"]
        
        # Compare columns
        if source_index["columns"] != target_index["columns"]:
            differences.append(Difference(
                diff_type=DiffType.INDEX_COLUMNS_CHANGED,
                severity=SeverityLevel.HIGH,
                object_type=ObjectType.INDEX,
                schema_name=schema_name,
                object_name=table_name,
                sub_object_name=index_name,
                source_value=source_index["columns"],
                target_value=target_index["columns"],
                description=f"Index columns changed: {source_index['columns']} → {target_index['columns']}",
                can_auto_fix=True,
                fix_order=self.get_fix_order(),
                warnings=["Index rebuild required", "May impact query performance during rebuild"]
            ))
        
        # Compare uniqueness
        if source_index["is_unique"] != target_index["is_unique"]:
            differences.append(Difference(
                diff_type=DiffType.INDEX_UNIQUE_CHANGED,
                severity=SeverityLevel.HIGH if target_index["is_unique"] else SeverityLevel.MEDIUM,
                object_type=ObjectType.INDEX,
                schema_name=schema_name,
                object_name=table_name,
                sub_object_name=index_name,
                source_value="UNIQUE" if source_index["is_unique"] else "NON-UNIQUE",
                target_value="UNIQUE" if target_index["is_unique"] else "NON-UNIQUE",
                description=f"Index uniqueness changed",
                can_auto_fix=True,
                fix_order=self.get_fix_order(),
                warnings=["Check for duplicate values"] if target_index["is_unique"] else []
            ))
        
        # Compare index type
        if source_index["index_type"] != target_index["index_type"]:
            differences.append(Difference(
                diff_type=DiffType.INDEX_TYPE_CHANGED,
                severity=SeverityLevel.MEDIUM,
                object_type=ObjectType.INDEX,
                schema_name=schema_name,
                object_name=table_name,
                sub_object_name=index_name,
                source_value=source_index["index_type"],
                target_value=target_index["index_type"],
                description=f"Index type changed: {source_index['index_type']} → {target_index['index_type']}",
                can_auto_fix=True,
                fix_order=self.get_fix_order(),
                warnings=["Performance characteristics may change"]
            ))
        
        return differences
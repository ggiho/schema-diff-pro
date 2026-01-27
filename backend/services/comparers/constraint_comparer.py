from typing import Dict, Any, List, AsyncGenerator, Set, Tuple
import asyncio
import logging
from sqlalchemy import text

from .base_comparer import BaseComparer
from models.base import (
    Difference, ObjectType, DiffType, SeverityLevel, ComparisonProgress
)
from core.database import DatabaseConnection
from core.config import settings

logger = logging.getLogger(__name__)


class ConstraintComparer(BaseComparer):
    """Compare database constraints (PK, FK, CHECK, UNIQUE)"""
    
    object_type = ObjectType.CONSTRAINT
    
    async def discover_objects(self, connection: DatabaseConnection) -> Dict[str, Any]:
        """Discover all constraints"""
        # Foreign keys
        fk_query = text("""
        SELECT 
            kcu.CONSTRAINT_SCHEMA,
            kcu.TABLE_NAME,
            kcu.CONSTRAINT_NAME,
            'FOREIGN KEY' as CONSTRAINT_TYPE,
            GROUP_CONCAT(kcu.COLUMN_NAME ORDER BY kcu.ORDINAL_POSITION) as COLUMNS,
            kcu.REFERENCED_TABLE_SCHEMA,
            kcu.REFERENCED_TABLE_NAME,
            GROUP_CONCAT(kcu.REFERENCED_COLUMN_NAME ORDER BY kcu.ORDINAL_POSITION) as REFERENCED_COLUMNS,
            rc.UPDATE_RULE,
            rc.DELETE_RULE
        FROM information_schema.KEY_COLUMN_USAGE kcu
        JOIN information_schema.REFERENTIAL_CONSTRAINTS rc
            ON kcu.CONSTRAINT_SCHEMA = rc.CONSTRAINT_SCHEMA
            AND kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
        WHERE kcu.CONSTRAINT_SCHEMA NOT IN :system_dbs
            AND kcu.REFERENCED_TABLE_NAME IS NOT NULL
        GROUP BY 
            kcu.CONSTRAINT_SCHEMA,
            kcu.TABLE_NAME,
            kcu.CONSTRAINT_NAME,
            kcu.REFERENCED_TABLE_SCHEMA,
            kcu.REFERENCED_TABLE_NAME,
            rc.UPDATE_RULE,
            rc.DELETE_RULE
        """)
        
        # Primary keys only (UNIQUE constraints are handled by IndexComparer as UNIQUE INDEX)
        # This avoids duplicate detection since MySQL implements UNIQUE constraints as UNIQUE indexes
        pk_query = text("""
        SELECT 
            tc.CONSTRAINT_SCHEMA,
            tc.TABLE_NAME,
            tc.CONSTRAINT_NAME,
            tc.CONSTRAINT_TYPE,
            GROUP_CONCAT(kcu.COLUMN_NAME ORDER BY kcu.ORDINAL_POSITION) as COLUMNS,
            NULL as REFERENCED_TABLE_SCHEMA,
            NULL as REFERENCED_TABLE_NAME,
            NULL as REFERENCED_COLUMNS,
            NULL as UPDATE_RULE,
            NULL as DELETE_RULE
        FROM information_schema.TABLE_CONSTRAINTS tc
        JOIN information_schema.KEY_COLUMN_USAGE kcu
            ON tc.CONSTRAINT_SCHEMA = kcu.CONSTRAINT_SCHEMA
            AND tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
            AND tc.TABLE_NAME = kcu.TABLE_NAME
        WHERE tc.CONSTRAINT_SCHEMA NOT IN :system_dbs
            AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
        GROUP BY 
            tc.CONSTRAINT_SCHEMA,
            tc.TABLE_NAME,
            tc.CONSTRAINT_NAME,
            tc.CONSTRAINT_TYPE
        """)
        
        # Check constraints (MySQL 8.0.16+)
        check_query = text("""
        SELECT 
            CONSTRAINT_SCHEMA,
            TABLE_NAME,
            CONSTRAINT_NAME,
            'CHECK' as CONSTRAINT_TYPE,
            NULL as COLUMNS,
            NULL as REFERENCED_TABLE_SCHEMA,
            NULL as REFERENCED_TABLE_NAME,
            NULL as REFERENCED_COLUMNS,
            NULL as UPDATE_RULE,
            NULL as DELETE_RULE
        FROM information_schema.CHECK_CONSTRAINTS
        WHERE CONSTRAINT_SCHEMA NOT IN :system_dbs
        """)
        
        constraints = {}
        
        # Get foreign keys
        try:
            fk_results = await connection.execute_query(
                fk_query,
                {"system_dbs": tuple(settings.SYSTEM_DATABASES)}
            )
            
            for row in fk_results:
                schema_name = row[0]
                table_name = row[1]
                
                if not self.should_compare_object(schema_name, table_name):
                    continue
                
                constraint_key = f"{schema_name}.{table_name}.{row[2]}"
                constraints[constraint_key] = {
                    "schema_name": schema_name,
                    "table_name": table_name,
                    "constraint_name": row[2],
                    "constraint_type": row[3],
                    "columns": row[4],
                    "referenced_table_schema": row[5],
                    "referenced_table_name": row[6],
                    "referenced_columns": row[7],
                    "update_rule": row[8],
                    "delete_rule": row[9]
                }
        except Exception as e:
            logger.warning(f"Error fetching foreign keys: {e}")
        
        # Get primary keys (UNIQUE is handled by IndexComparer)
        try:
            pk_results = await connection.execute_query(
                pk_query,
                {"system_dbs": tuple(settings.SYSTEM_DATABASES)}
            )
            
            for row in pk_results:
                schema_name = row[0]
                table_name = row[1]
                
                if not self.should_compare_object(schema_name, table_name):
                    continue
                
                constraint_key = f"{schema_name}.{table_name}.{row[2]}"
                constraints[constraint_key] = {
                    "schema_name": schema_name,
                    "table_name": table_name,
                    "constraint_name": row[2],
                    "constraint_type": row[3],
                    "columns": row[4],
                    "referenced_table_schema": None,
                    "referenced_table_name": None,
                    "referenced_columns": None,
                    "update_rule": None,
                    "delete_rule": None
                }
        except Exception as e:
            logger.warning(f"Error fetching primary/unique keys: {e}")
        
        # Get check constraints (if supported)
        try:
            check_results = await connection.execute_query(
                check_query,
                {"system_dbs": tuple(settings.SYSTEM_DATABASES)}
            )
            
            for row in check_results:
                schema_name = row[0]
                table_name = row[1]
                
                if not self.should_compare_object(schema_name, table_name):
                    continue
                
                constraint_key = f"{schema_name}.{table_name}.{row[2]}"
                constraints[constraint_key] = {
                    "schema_name": schema_name,
                    "table_name": table_name,
                    "constraint_name": row[2],
                    "constraint_type": row[3],
                    "columns": None,
                    "referenced_table_schema": None,
                    "referenced_table_name": None,
                    "referenced_columns": None,
                    "update_rule": None,
                    "delete_rule": None
                }
        except Exception as e:
            logger.info(f"Check constraints not supported or accessible: {e}")
        
        return constraints
    
    def _create_constraint_signature(self, constraint: Dict[str, Any]) -> str:
        """Create a signature for a constraint based on its definition (not name)"""
        # For UNIQUE and PRIMARY KEY: table + type + columns
        # For FOREIGN KEY: table + type + columns + referenced table/columns + rules
        base = f"{constraint['schema_name']}.{constraint['table_name']}|{constraint['constraint_type']}|{constraint['columns']}"
        
        if constraint['constraint_type'] == 'FOREIGN KEY':
            base += f"|{constraint['referenced_table_schema']}.{constraint['referenced_table_name']}|{constraint['referenced_columns']}"
            base += f"|{constraint['update_rule']}|{constraint['delete_rule']}"
        
        return base
    
    async def compare(self) -> AsyncGenerator[ComparisonProgress, None]:
        """Override compare to detect renamed constraints"""
        # Discovery phase
        yield ComparisonProgress(
            comparison_id=self.comparison_id,
            phase="discovery",
            current=0,
            total=2,
            current_object=f"Discovering {self.object_type.value}s in source",
            message=f"Starting {self.object_type.value} discovery"
        )
        
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
        
        # Build signature-based lookup for rename detection
        source_by_signature: Dict[str, Dict[str, Any]] = {}
        target_by_signature: Dict[str, Dict[str, Any]] = {}
        
        for key, const in source_objects.items():
            sig = self._create_constraint_signature(const)
            source_by_signature[sig] = const
            logger.debug(f"Source constraint: {key} -> signature: {sig}")
        
        for key, const in target_objects.items():
            sig = self._create_constraint_signature(const)
            target_by_signature[sig] = const
            logger.debug(f"Target constraint: {key} -> signature: {sig}")
        
        # Log matching info
        for sig in source_by_signature:
            if sig in target_by_signature:
                src = source_by_signature[sig]
                tgt = target_by_signature[sig]
                if src['constraint_name'] != tgt['constraint_name']:
                    logger.info(f"Detected constraint rename: {src['constraint_name']} -> {tgt['constraint_name']} (sig: {sig})")
        
        # Track processed constraints to avoid duplicates
        processed_source: Set[str] = set()
        processed_target: Set[str] = set()
        renamed_pairs: List[Tuple[Dict, Dict]] = []
        
        # First pass: detect renames (same signature, different name)
        for sig, source_const in source_by_signature.items():
            if sig in target_by_signature:
                target_const = target_by_signature[sig]
                source_key = f"{source_const['schema_name']}.{source_const['table_name']}.{source_const['constraint_name']}"
                target_key = f"{target_const['schema_name']}.{target_const['table_name']}.{target_const['constraint_name']}"
                
                # Same signature but different name = rename
                if source_const['constraint_name'] != target_const['constraint_name']:
                    # Skip PRIMARY KEY - can't be renamed
                    if source_const['constraint_type'] != 'PRIMARY KEY':
                        renamed_pairs.append((source_const, target_const))
                    processed_source.add(source_key)
                    processed_target.add(target_key)
                else:
                    # Same name and same signature = match
                    processed_source.add(source_key)
                    processed_target.add(target_key)
        
        # Comparison phase
        total_objects = len(set(list(source_objects.keys()) + list(target_objects.keys())))
        
        if total_objects > 0:
            current = 0
            
            # Process renamed constraints
            for source_const, target_const in renamed_pairs:
                current += 1
                yield ComparisonProgress(
                    comparison_id=self.comparison_id,
                    phase="comparison",
                    current=current,
                    total=total_objects,
                    current_object=f"{source_const['constraint_name']} → {target_const['constraint_name']}",
                    message=f"Detected constraint rename"
                )
                
                self.differences.append(Difference(
                    diff_type=DiffType.CONSTRAINT_RENAMED,
                    severity=SeverityLevel.LOW,
                    object_type=ObjectType.CONSTRAINT,
                    schema_name=source_const['schema_name'],
                    object_name=source_const['table_name'],
                    sub_object_name=source_const['constraint_name'],
                    source_value=source_const,
                    target_value=target_const,
                    description=f"Constraint renamed: {source_const['constraint_name']} → {target_const['constraint_name']}",
                    can_auto_fix=True,
                    fix_order=self.get_fix_order()
                ))
            
            # Process remaining constraints
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
                    obj_differences = await self.compare_single_object(obj_name, source_obj, target_obj)
                    self.differences.extend(obj_differences)
                elif source_obj and not target_obj:
                    source_key = f"{source_obj['schema_name']}.{source_obj['table_name']}.{source_obj['constraint_name']}"
                    if source_key not in processed_source:
                        self.differences.append(self.create_missing_difference(
                            obj_name, source_obj, "target"
                        ))
                elif not source_obj and target_obj:
                    target_key = f"{target_obj['schema_name']}.{target_obj['table_name']}.{target_obj['constraint_name']}"
                    if target_key not in processed_target:
                        self.differences.append(self.create_missing_difference(
                            obj_name, target_obj, "source"
                        ))
    
    async def compare_objects(
        self,
        source_objects: Dict[str, Any],
        target_objects: Dict[str, Any]
    ) -> List[Difference]:
        """Compare discovered objects and return differences"""
        # Handled in overridden compare() method
        return []
    
    async def compare_single_object(
        self,
        constraint_key: str,
        source_constraint: Dict[str, Any],
        target_constraint: Dict[str, Any]
    ) -> List[Difference]:
        """Compare a single constraint"""
        differences = []
        schema_name = source_constraint["schema_name"]
        table_name = source_constraint["table_name"]
        constraint_name = source_constraint["constraint_name"]
        
        # For foreign keys, compare all properties
        if source_constraint["constraint_type"] == "FOREIGN KEY":
            # Compare referenced table
            if (source_constraint["referenced_table_schema"] != target_constraint["referenced_table_schema"] or
                source_constraint["referenced_table_name"] != target_constraint["referenced_table_name"]):
                differences.append(Difference(
                    diff_type=DiffType.CONSTRAINT_DEFINITION_CHANGED,
                    severity=SeverityLevel.HIGH,
                    object_type=ObjectType.CONSTRAINT,
                    schema_name=schema_name,
                    object_name=table_name,
                    sub_object_name=constraint_name,
                    source_value=f"{source_constraint['referenced_table_schema']}.{source_constraint['referenced_table_name']}",
                    target_value=f"{target_constraint['referenced_table_schema']}.{target_constraint['referenced_table_name']}",
                    description=f"Foreign key references different table",
                    can_auto_fix=True,
                    fix_order=self.get_fix_order(),
                    warnings=["Ensure referential integrity"]
                ))
            
            # Compare columns
            if (source_constraint["columns"] != target_constraint["columns"] or
                source_constraint["referenced_columns"] != target_constraint["referenced_columns"]):
                differences.append(Difference(
                    diff_type=DiffType.CONSTRAINT_DEFINITION_CHANGED,
                    severity=SeverityLevel.HIGH,
                    object_type=ObjectType.CONSTRAINT,
                    schema_name=schema_name,
                    object_name=table_name,
                    sub_object_name=constraint_name,
                    source_value=f"{source_constraint['columns']} -> {source_constraint['referenced_columns']}",
                    target_value=f"{target_constraint['columns']} -> {target_constraint['referenced_columns']}",
                    description=f"Foreign key columns changed",
                    can_auto_fix=True,
                    fix_order=self.get_fix_order()
                ))
            
            # Compare rules
            if (source_constraint["update_rule"] != target_constraint["update_rule"] or
                source_constraint["delete_rule"] != target_constraint["delete_rule"]):
                differences.append(Difference(
                    diff_type=DiffType.CONSTRAINT_DEFINITION_CHANGED,
                    severity=SeverityLevel.MEDIUM,
                    object_type=ObjectType.CONSTRAINT,
                    schema_name=schema_name,
                    object_name=table_name,
                    sub_object_name=constraint_name,
                    source_value=f"UPDATE: {source_constraint['update_rule']}, DELETE: {source_constraint['delete_rule']}",
                    target_value=f"UPDATE: {target_constraint['update_rule']}, DELETE: {target_constraint['delete_rule']}",
                    description=f"Foreign key rules changed",
                    can_auto_fix=True,
                    fix_order=self.get_fix_order()
                ))
        
        # For other constraints, compare columns
        elif source_constraint["columns"] != target_constraint["columns"]:
            differences.append(Difference(
                diff_type=DiffType.CONSTRAINT_DEFINITION_CHANGED,
                severity=SeverityLevel.HIGH if source_constraint["constraint_type"] == "PRIMARY KEY" else SeverityLevel.MEDIUM,
                object_type=ObjectType.CONSTRAINT,
                schema_name=schema_name,
                object_name=table_name,
                sub_object_name=constraint_name,
                source_value=source_constraint["columns"],
                target_value=target_constraint["columns"],
                description=f"{source_constraint['constraint_type']} columns changed",
                can_auto_fix=True,
                fix_order=self.get_fix_order(),
                warnings=["Primary key change requires table rebuild"] if source_constraint["constraint_type"] == "PRIMARY KEY" else []
            ))
        
        return differences
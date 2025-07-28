from typing import Dict, Any, List
import logging
from sqlalchemy import text

from .base_comparer import BaseComparer
from models.base import (
    Difference, ObjectType, DiffType, SeverityLevel
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
        
        # Primary keys and unique constraints
        pk_unique_query = text("""
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
            AND tc.CONSTRAINT_TYPE IN ('PRIMARY KEY', 'UNIQUE')
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
        
        # Get primary keys and unique constraints
        try:
            pk_results = await connection.execute_query(
                pk_unique_query,
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
    
    async def compare_objects(
        self,
        source_objects: Dict[str, Any],
        target_objects: Dict[str, Any]
    ) -> List[Difference]:
        """Compare discovered objects and return differences"""
        # This method is required by the abstract base class
        # The actual comparison logic is handled in the base class compare() method
        # which calls compare_single_object for each object
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
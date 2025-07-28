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
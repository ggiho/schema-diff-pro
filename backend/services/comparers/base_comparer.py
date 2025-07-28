from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Set, AsyncGenerator
import asyncio
import logging
from datetime import datetime

from models.base import (
    Difference, ComparisonResult, ComparisonProgress,
    ObjectType, DiffType, SeverityLevel, ComparisonOptions
)
from core.database import DatabaseConnection

logger = logging.getLogger(__name__)


class BaseComparer(ABC):
    """Base class for all database object comparers"""
    
    object_type: ObjectType
    
    def __init__(
        self,
        source_conn: DatabaseConnection,
        target_conn: DatabaseConnection,
        options: ComparisonOptions,
        comparison_id: str
    ):
        self.source_conn = source_conn
        self.target_conn = target_conn
        self.options = options
        self.comparison_id = comparison_id
        self.differences: List[Difference] = []
        
    @abstractmethod
    async def discover_objects(self, connection: DatabaseConnection) -> Dict[str, Any]:
        """Discover database objects of this type"""
        pass
    
    @abstractmethod
    async def compare_objects(
        self,
        source_objects: Dict[str, Any],
        target_objects: Dict[str, Any]
    ) -> List[Difference]:
        """Compare discovered objects and return differences"""
        pass
    
    async def compare(self) -> AsyncGenerator[ComparisonProgress, None]:
        """Main comparison logic with progress updates"""
        # Discovery phase
        yield ComparisonProgress(
            comparison_id=self.comparison_id,
            phase="discovery",
            current=0,
            total=2,
            current_object=f"Discovering {self.object_type.value}s in source",
            message=f"Starting {self.object_type.value} discovery"
        )
        
        # Parallel discovery
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
        
        # Comparison phase
        total_objects = len(set(list(source_objects.keys()) + list(target_objects.keys())))
        
        if total_objects > 0:
            current = 0
            for obj_name in set(list(source_objects.keys()) + list(target_objects.keys())):
                current += 1
                yield ComparisonProgress(
                    comparison_id=self.comparison_id,
                    phase="comparison",
                    current=current,
                    total=total_objects,
                    current_object=obj_name,
                    message=f"Comparing {self.object_type.value}: {obj_name}"
                )
                
                # Compare individual object
                source_obj = source_objects.get(obj_name)
                target_obj = target_objects.get(obj_name)
                
                if source_obj and target_obj:
                    # Object exists in both - compare details
                    obj_differences = await self.compare_single_object(obj_name, source_obj, target_obj)
                    self.differences.extend(obj_differences)
                elif source_obj and not target_obj:
                    # Object only in source
                    self.differences.append(self.create_missing_difference(
                        obj_name, source_obj, "target"
                    ))
                elif not source_obj and target_obj:
                    # Object only in target
                    self.differences.append(self.create_missing_difference(
                        obj_name, target_obj, "source"
                    ))
    
    async def compare_single_object(
        self,
        obj_name: str,
        source_obj: Any,
        target_obj: Any
    ) -> List[Difference]:
        """Compare a single object that exists in both databases"""
        # Default implementation - override in subclasses
        return []
    
    def create_missing_difference(
        self,
        obj_name: str,
        obj_data: Any,
        missing_in: str
    ) -> Difference:
        """Create a difference for an object missing in one database"""
        diff_type_map = {
            ObjectType.TABLE: (DiffType.TABLE_MISSING_SOURCE, DiffType.TABLE_MISSING_TARGET),
            ObjectType.INDEX: (DiffType.INDEX_MISSING_SOURCE, DiffType.INDEX_MISSING_TARGET),
            ObjectType.CONSTRAINT: (DiffType.CONSTRAINT_MISSING_SOURCE, DiffType.CONSTRAINT_MISSING_TARGET),
            ObjectType.PROCEDURE: (DiffType.ROUTINE_MISSING_SOURCE, DiffType.ROUTINE_MISSING_TARGET),
            ObjectType.FUNCTION: (DiffType.ROUTINE_MISSING_SOURCE, DiffType.ROUTINE_MISSING_TARGET),
            ObjectType.VIEW: (DiffType.VIEW_MISSING_SOURCE, DiffType.VIEW_MISSING_TARGET),
            ObjectType.TRIGGER: (DiffType.TRIGGER_MISSING_SOURCE, DiffType.TRIGGER_MISSING_TARGET),
        }
        
        source_type, target_type = diff_type_map.get(
            self.object_type,
            (DiffType.TABLE_MISSING_SOURCE, DiffType.TABLE_MISSING_TARGET)
        )
        
        return Difference(
            diff_type=source_type if missing_in == "source" else target_type,
            severity=SeverityLevel.HIGH,
            object_type=self.object_type,
            schema_name=obj_data.get("schema_name"),
            object_name=obj_name,
            source_value=None if missing_in == "source" else obj_data,
            target_value=obj_data if missing_in == "source" else None,
            description=f"{self.object_type.value.capitalize()} '{obj_name}' exists only in {'target' if missing_in == 'source' else 'source'} database",
            can_auto_fix=True,
            fix_order=self.get_fix_order()
        )
    
    def get_fix_order(self) -> int:
        """Get the order for fixing this type of difference"""
        # Order matters for dependencies
        order_map = {
            ObjectType.SCHEMA: 1,
            ObjectType.TABLE: 2,
            ObjectType.COLUMN: 3,
            ObjectType.CONSTRAINT: 4,  # After columns
            ObjectType.INDEX: 5,       # After columns
            ObjectType.VIEW: 6,        # After tables
            ObjectType.TRIGGER: 7,     # After tables
            ObjectType.PROCEDURE: 8,
            ObjectType.FUNCTION: 9,
            ObjectType.EVENT: 10,
        }
        return order_map.get(self.object_type, 99)
    
    def should_compare_object(self, schema_name: str, object_name: str) -> bool:
        """Check if an object should be compared based on options"""
        # Check schema filters
        if self.options.included_schemas and schema_name not in self.options.included_schemas:
            return False
        if self.options.excluded_schemas and schema_name in self.options.excluded_schemas:
            return False
            
        # Check table filters (if applicable)
        if self.object_type == ObjectType.TABLE:
            if self.options.included_tables and object_name not in self.options.included_tables:
                return False
            if self.options.excluded_tables and object_name in self.options.excluded_tables:
                return False
                
        return True
    
    def determine_severity(self, diff_type: DiffType) -> SeverityLevel:
        """Determine severity level for a difference type"""
        # Override in subclasses for more specific logic
        critical_types = [
            DiffType.TABLE_MISSING_TARGET,
            DiffType.COLUMN_REMOVED,
            DiffType.CONSTRAINT_MISSING_TARGET,
        ]
        
        high_types = [
            DiffType.TABLE_MISSING_SOURCE,
            DiffType.COLUMN_TYPE_CHANGED,
            DiffType.COLUMN_NULLABLE_CHANGED,
            DiffType.INDEX_MISSING_SOURCE,
            DiffType.INDEX_MISSING_TARGET,
        ]
        
        medium_types = [
            DiffType.COLUMN_DEFAULT_CHANGED,
            DiffType.INDEX_TYPE_CHANGED,
            DiffType.VIEW_DEFINITION_CHANGED,
        ]
        
        if diff_type in critical_types:
            return SeverityLevel.CRITICAL
        elif diff_type in high_types:
            return SeverityLevel.HIGH
        elif diff_type in medium_types:
            return SeverityLevel.MEDIUM
        else:
            return SeverityLevel.LOW
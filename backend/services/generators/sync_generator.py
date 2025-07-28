from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict, deque
import logging

from models.base import (
    Difference, SyncScript, DiffType, ObjectType, SeverityLevel
)
from datetime import datetime

logger = logging.getLogger(__name__)


class SyncScriptGenerator:
    """Generate SQL synchronization scripts from differences"""
    
    def __init__(self, differences: List[Difference], comparison_id: str):
        self.differences = differences
        self.comparison_id = comparison_id
        self.dependency_graph = defaultdict(set)  # Using indices as keys
        self.warnings = []
        
    def generate_sync_script(self) -> SyncScript:
        """Generate forward and rollback scripts"""
        # Build dependency graph
        self._build_dependency_graph()
        
        # Sort differences by dependencies
        ordered_differences = self._topological_sort()
        
        # Generate SQL statements
        forward_statements = []
        rollback_statements = []
        
        for diff in ordered_differences:
            try:
                forward, rollback = self._generate_statements(diff)
                if forward:
                    forward_statements.append(forward)
                if rollback:
                    rollback_statements.append(rollback)
            except Exception as e:
                logger.warning(f"Failed to generate statement for {diff.object_name}: {e}")
                self.warnings.append(f"Could not generate SQL for {diff.object_name}: {str(e)}")
        
        # Analyze impact
        impact = self._analyze_impact(ordered_differences)
        
        return SyncScript(
            comparison_id=self.comparison_id,
            forward_script=self._format_script(forward_statements, "Forward Migration"),
            rollback_script=self._format_script(list(reversed(rollback_statements)), "Rollback Script"),
            warnings=self.warnings,
            estimated_impact=impact,
            estimated_duration=self._estimate_duration(ordered_differences),
            requires_downtime=self._requires_downtime(ordered_differences),
            data_loss_risk=self._has_data_loss_risk(ordered_differences)
        )
    
    def _build_dependency_graph(self):
        """Build dependency graph for proper ordering"""
        # For now, we'll skip complex dependency graph building
        # and just rely on fix_order for sorting
        pass
    
    def _topological_sort(self) -> List[Difference]:
        """Sort differences considering dependencies"""
        # For now, use fix_order and severity
        return sorted(
            self.differences,
            key=lambda d: (d.fix_order, -self._severity_to_int(d.severity), d.object_name)
        )
    
    def _severity_to_int(self, severity: SeverityLevel) -> int:
        """Convert severity to integer for sorting"""
        severity_map = {
            SeverityLevel.CRITICAL: 4,
            SeverityLevel.HIGH: 3,
            SeverityLevel.MEDIUM: 2,
            SeverityLevel.LOW: 1,
            SeverityLevel.INFO: 0
        }
        return severity_map.get(severity, 0)
    
    def _generate_statements(self, diff: Difference) -> Tuple[Optional[str], Optional[str]]:
        """Generate forward and rollback SQL for a difference"""
        generators = {
            # Tables
            DiffType.TABLE_MISSING_SOURCE: self._gen_drop_table,
            DiffType.TABLE_MISSING_TARGET: self._gen_create_table,
            
            # Columns
            DiffType.COLUMN_ADDED: self._gen_add_column,
            DiffType.COLUMN_REMOVED: self._gen_drop_column,
            DiffType.COLUMN_TYPE_CHANGED: self._gen_alter_column_type,
            DiffType.COLUMN_DEFAULT_CHANGED: self._gen_alter_column_default,
            DiffType.COLUMN_NULLABLE_CHANGED: self._gen_alter_column_nullable,
            
            # Indexes
            DiffType.INDEX_MISSING_SOURCE: self._gen_drop_index,
            DiffType.INDEX_MISSING_TARGET: self._gen_create_index,
            DiffType.INDEX_COLUMNS_CHANGED: self._gen_recreate_index,
            DiffType.INDEX_TYPE_CHANGED: self._gen_recreate_index,
            DiffType.INDEX_UNIQUE_CHANGED: self._gen_recreate_index,
            
            # Constraints
            DiffType.CONSTRAINT_MISSING_SOURCE: self._gen_drop_constraint,
            DiffType.CONSTRAINT_MISSING_TARGET: self._gen_create_constraint,
            DiffType.CONSTRAINT_DEFINITION_CHANGED: self._gen_recreate_constraint,
        }
        
        generator = generators.get(diff.diff_type)
        if generator:
            return generator(diff)
        
        return None, None
    
    # Table generators
    def _gen_create_table(self, diff: Difference) -> Tuple[str, str]:
        """Generate CREATE TABLE statement"""
        # This would need the full table definition from source_value
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        
        # Simplified example - real implementation would use full table def
        forward = f"-- TODO: CREATE TABLE {table_name} AS IN SOURCE;"
        rollback = f"DROP TABLE IF EXISTS {table_name};"
        
        return forward, rollback
    
    def _gen_drop_table(self, diff: Difference) -> Tuple[str, str]:
        """Generate DROP TABLE statement"""
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        
        forward = f"DROP TABLE IF EXISTS {table_name};"
        rollback = f"-- TODO: RECREATE TABLE {table_name} FROM BACKUP;"
        
        self.warnings.append(f"Dropping table {table_name} - ensure data is backed up!")
        
        return forward, rollback
    
    # Column generators
    def _gen_add_column(self, diff: Difference) -> Tuple[str, str]:
        """Generate ADD COLUMN statement"""
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        column_name = f"`{diff.sub_object_name}`"
        
        if diff.target_value:
            col_def = diff.target_value
            column_type = col_def.get("column_type", "VARCHAR(255)")
            nullable = "NULL" if col_def.get("is_nullable", True) else "NOT NULL"
            default = f"DEFAULT {col_def.get('column_default')}" if col_def.get("column_default") else ""
            
            forward = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} {nullable} {default};"
            rollback = f"ALTER TABLE {table_name} DROP COLUMN {column_name};"
            
            return forward, rollback
        
        return None, None
    
    def _gen_drop_column(self, diff: Difference) -> Tuple[str, str]:
        """Generate DROP COLUMN statement"""
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        column_name = f"`{diff.sub_object_name}`"
        
        forward = f"ALTER TABLE {table_name} DROP COLUMN {column_name};"
        rollback = f"-- TODO: ADD COLUMN {column_name} BACK WITH ORIGINAL DEFINITION;"
        
        self.warnings.append(f"Dropping column {table_name}.{column_name} - data will be lost!")
        
        return forward, rollback
    
    def _gen_alter_column_type(self, diff: Difference) -> Tuple[str, str]:
        """Generate ALTER COLUMN TYPE statement"""
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        column_name = f"`{diff.sub_object_name}`"
        
        forward = f"ALTER TABLE {table_name} MODIFY COLUMN {column_name} {diff.target_value};"
        rollback = f"ALTER TABLE {table_name} MODIFY COLUMN {column_name} {diff.source_value};"
        
        return forward, rollback
    
    def _gen_alter_column_default(self, diff: Difference) -> Tuple[str, str]:
        """Generate ALTER COLUMN DEFAULT statement"""
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        column_name = f"`{diff.sub_object_name}`"
        
        if diff.target_value:
            forward = f"ALTER TABLE {table_name} ALTER COLUMN {column_name} SET DEFAULT {diff.target_value};"
        else:
            forward = f"ALTER TABLE {table_name} ALTER COLUMN {column_name} DROP DEFAULT;"
        
        if diff.source_value:
            rollback = f"ALTER TABLE {table_name} ALTER COLUMN {column_name} SET DEFAULT {diff.source_value};"
        else:
            rollback = f"ALTER TABLE {table_name} ALTER COLUMN {column_name} DROP DEFAULT;"
        
        return forward, rollback
    
    def _gen_alter_column_nullable(self, diff: Difference) -> Tuple[str, str]:
        """Generate ALTER COLUMN NULL/NOT NULL statement"""
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        column_name = f"`{diff.sub_object_name}`"
        
        # Need column type - in real implementation would get from metadata
        column_type = "VARCHAR(255)"  # Placeholder
        
        if diff.target_value == "NOT NULL":
            forward = f"ALTER TABLE {table_name} MODIFY COLUMN {column_name} {column_type} NOT NULL;"
            rollback = f"ALTER TABLE {table_name} MODIFY COLUMN {column_name} {column_type} NULL;"
        else:
            forward = f"ALTER TABLE {table_name} MODIFY COLUMN {column_name} {column_type} NULL;"
            rollback = f"ALTER TABLE {table_name} MODIFY COLUMN {column_name} {column_type} NOT NULL;"
        
        return forward, rollback
    
    # Index generators
    def _gen_create_index(self, diff: Difference) -> Tuple[str, str]:
        """Generate CREATE INDEX statement"""
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        index_name = f"`{diff.sub_object_name}`"
        
        if diff.target_value:
            idx_data = diff.target_value
            unique = "UNIQUE" if idx_data.get("is_unique") else ""
            columns = idx_data.get("columns", "")
            idx_type = f"USING {idx_data.get('index_type')}" if idx_data.get("index_type") != "BTREE" else ""
            
            forward = f"CREATE {unique} INDEX {index_name} ON {table_name} ({columns}) {idx_type};"
            rollback = f"DROP INDEX {index_name} ON {table_name};"
            
            return forward, rollback
        
        return None, None
    
    def _gen_drop_index(self, diff: Difference) -> Tuple[str, str]:
        """Generate DROP INDEX statement"""
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        index_name = f"`{diff.sub_object_name}`"
        
        forward = f"DROP INDEX {index_name} ON {table_name};"
        rollback = f"-- TODO: RECREATE INDEX {index_name};"
        
        return forward, rollback
    
    def _gen_recreate_index(self, diff: Difference) -> Tuple[str, str]:
        """Generate statements to recreate an index"""
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        index_name = f"`{diff.sub_object_name}`"
        
        # Drop and recreate
        drop_stmt = f"DROP INDEX {index_name} ON {table_name};"
        
        if diff.target_value:
            idx_data = diff.target_value
            unique = "UNIQUE" if idx_data.get("is_unique") else ""
            columns = idx_data.get("columns", "")
            idx_type = f"USING {idx_data.get('index_type')}" if idx_data.get("index_type") != "BTREE" else ""
            
            create_stmt = f"CREATE {unique} INDEX {index_name} ON {table_name} ({columns}) {idx_type};"
            
            forward = f"{drop_stmt}\n{create_stmt}"
            
            # Rollback would recreate with original definition
            rollback = f"-- TODO: RECREATE INDEX {index_name} WITH ORIGINAL DEFINITION;"
            
            return forward, rollback
        
        return None, None
    
    # Constraint generators
    def _gen_create_constraint(self, diff: Difference) -> Tuple[str, str]:
        """Generate CREATE CONSTRAINT statement"""
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        constraint_name = f"`{diff.sub_object_name}`"
        
        if diff.target_value:
            const_data = diff.target_value
            const_type = const_data.get("constraint_type")
            
            if const_type == "FOREIGN KEY":
                columns = const_data.get("columns", "")
                ref_table = f"`{const_data.get('referenced_table_schema')}`.`{const_data.get('referenced_table_name')}`"
                ref_columns = const_data.get("referenced_columns", "")
                update_rule = const_data.get("update_rule", "RESTRICT")
                delete_rule = const_data.get("delete_rule", "RESTRICT")
                
                forward = f"""ALTER TABLE {table_name} 
ADD CONSTRAINT {constraint_name} 
FOREIGN KEY ({columns}) 
REFERENCES {ref_table} ({ref_columns})
ON UPDATE {update_rule} ON DELETE {delete_rule};"""
                
            elif const_type == "PRIMARY KEY":
                columns = const_data.get("columns", "")
                forward = f"ALTER TABLE {table_name} ADD PRIMARY KEY ({columns});"
                
            elif const_type == "UNIQUE":
                columns = const_data.get("columns", "")
                forward = f"ALTER TABLE {table_name} ADD CONSTRAINT {constraint_name} UNIQUE ({columns});"
                
            else:
                forward = f"-- TODO: ADD {const_type} CONSTRAINT {constraint_name};"
            
            rollback = f"ALTER TABLE {table_name} DROP CONSTRAINT {constraint_name};"
            
            return forward, rollback
        
        return None, None
    
    def _gen_drop_constraint(self, diff: Difference) -> Tuple[str, str]:
        """Generate DROP CONSTRAINT statement"""
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        constraint_name = f"`{diff.sub_object_name}`"
        
        forward = f"ALTER TABLE {table_name} DROP CONSTRAINT {constraint_name};"
        rollback = f"-- TODO: RECREATE CONSTRAINT {constraint_name};"
        
        return forward, rollback
    
    def _gen_recreate_constraint(self, diff: Difference) -> Tuple[str, str]:
        """Generate statements to recreate a constraint"""
        # Similar to recreate index
        return self._gen_drop_constraint(diff)
    
    def _format_script(self, statements: List[str], title: str) -> str:
        """Format SQL script with header and sections"""
        script = f"""-- {title}
-- Generated by Schema Diff Pro
-- Comparison ID: {self.comparison_id}
-- Generated at: {datetime.now().isoformat()}
-- Total statements: {len(statements)}

SET FOREIGN_KEY_CHECKS = 0;
SET SQL_MODE = 'NO_AUTO_VALUE_ON_ZERO';

"""
        
        current_type = None
        for stmt in statements:
            # Group by operation type
            if "CREATE TABLE" in stmt:
                if current_type != "TABLES":
                    script += "\n-- TABLE CREATION\n"
                    current_type = "TABLES"
            elif "ALTER TABLE" in stmt and "COLUMN" in stmt:
                if current_type != "COLUMNS":
                    script += "\n-- COLUMN MODIFICATIONS\n"
                    current_type = "COLUMNS"
            elif "INDEX" in stmt:
                if current_type != "INDEXES":
                    script += "\n-- INDEX MODIFICATIONS\n"
                    current_type = "INDEXES"
            elif "CONSTRAINT" in stmt:
                if current_type != "CONSTRAINTS":
                    script += "\n-- CONSTRAINT MODIFICATIONS\n"
                    current_type = "CONSTRAINTS"
            
            script += stmt + "\n\n"
        
        script += """
SET FOREIGN_KEY_CHECKS = 1;

-- End of script
"""
        
        return script
    
    def _analyze_impact(self, differences: List[Difference]) -> Dict[str, Any]:
        """Analyze the impact of applying changes"""
        impact = {
            "total_changes": len(differences),
            "tables_affected": set(),
            "estimated_rows_affected": 0,
            "index_rebuilds": 0,
            "constraint_changes": 0,
            "data_type_changes": 0,
            "potential_locks": [],
            "risks": []
        }
        
        for diff in differences:
            # Track affected tables
            if diff.schema_name and diff.object_name:
                impact["tables_affected"].add(f"{diff.schema_name}.{diff.object_name}")
            
            # Count different types of changes
            if diff.object_type == ObjectType.INDEX:
                impact["index_rebuilds"] += 1
                impact["potential_locks"].append(f"Index operation on {diff.object_name}")
            
            elif diff.object_type == ObjectType.CONSTRAINT:
                impact["constraint_changes"] += 1
            
            elif diff.diff_type == DiffType.COLUMN_TYPE_CHANGED:
                impact["data_type_changes"] += 1
                impact["potential_locks"].append(f"Column type change on {diff.object_name}.{diff.sub_object_name}")
                impact["risks"].append(f"Data conversion required for {diff.object_name}.{diff.sub_object_name}")
            
            # Identify high-risk operations
            if diff.severity == SeverityLevel.CRITICAL:
                impact["risks"].append(diff.description)
        
        impact["tables_affected"] = list(impact["tables_affected"])
        
        return impact
    
    def _estimate_duration(self, differences: List[Difference]) -> int:
        """Estimate execution duration in seconds"""
        # Very rough estimates
        duration = 0
        
        for diff in differences:
            if diff.object_type == ObjectType.TABLE:
                duration += 5  # Table operations are fast
            elif diff.object_type == ObjectType.INDEX:
                duration += 30  # Index rebuilds can be slow
            elif diff.diff_type == DiffType.COLUMN_TYPE_CHANGED:
                duration += 60  # Data conversion can be very slow
            else:
                duration += 2  # Most other operations are quick
        
        return duration
    
    def _requires_downtime(self, differences: List[Difference]) -> bool:
        """Check if changes require downtime"""
        # In MySQL 5.7+, most operations can be done online
        # But some still require locks
        
        for diff in differences:
            # Primary key changes usually require downtime
            if (diff.object_type == ObjectType.CONSTRAINT and 
                "PRIMARY KEY" in str(diff.target_value)):
                return True
            
            # Large data type changes might require downtime
            if (diff.diff_type == DiffType.COLUMN_TYPE_CHANGED and
                diff.severity == SeverityLevel.CRITICAL):
                return True
        
        return False
    
    def _has_data_loss_risk(self, differences: List[Difference]) -> bool:
        """Check if changes risk data loss"""
        
        for diff in differences:
            if diff.diff_type in [
                DiffType.TABLE_MISSING_SOURCE,
                DiffType.COLUMN_REMOVED,
                DiffType.COLUMN_TYPE_CHANGED
            ]:
                return True
            
            # Check warnings
            if any("data loss" in w.lower() for w in diff.warnings):
                return True
        
        return False
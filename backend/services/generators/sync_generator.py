from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict, deque
import logging
import copy

from models.base import (
    Difference, SyncScript, DiffType, ObjectType, SeverityLevel, SyncDirection
)
from datetime import datetime

logger = logging.getLogger(__name__)

# Mapping for reversing diff types when changing sync direction
REVERSE_DIFF_TYPE_MAP: Dict[DiffType, DiffType] = {
    # Tables
    DiffType.TABLE_MISSING_SOURCE: DiffType.TABLE_MISSING_TARGET,
    DiffType.TABLE_MISSING_TARGET: DiffType.TABLE_MISSING_SOURCE,
    # Columns
    DiffType.COLUMN_ADDED: DiffType.COLUMN_REMOVED,
    DiffType.COLUMN_REMOVED: DiffType.COLUMN_ADDED,
    # Indexes
    DiffType.INDEX_MISSING_SOURCE: DiffType.INDEX_MISSING_TARGET,
    DiffType.INDEX_MISSING_TARGET: DiffType.INDEX_MISSING_SOURCE,
    DiffType.INDEX_RENAMED: DiffType.INDEX_RENAMED,  # Same in both directions, just swap names
    # Constraints
    DiffType.CONSTRAINT_MISSING_SOURCE: DiffType.CONSTRAINT_MISSING_TARGET,
    DiffType.CONSTRAINT_MISSING_TARGET: DiffType.CONSTRAINT_MISSING_SOURCE,
    DiffType.CONSTRAINT_RENAMED: DiffType.CONSTRAINT_RENAMED,  # Same in both directions, just swap names
}


class SyncScriptGenerator:
    """Generate SQL synchronization scripts from differences"""
    
    def __init__(
        self, 
        differences: List[Difference], 
        comparison_id: str,
        direction: SyncDirection = SyncDirection.SOURCE_TO_TARGET
    ):
        self.original_differences = differences
        self.comparison_id = comparison_id
        self.direction = direction
        self.dependency_graph = defaultdict(set)  # Using indices as keys
        self.warnings = []
        
        # Transform differences based on direction
        self.differences = self._transform_differences_for_direction(differences, direction)
    
    def _transform_differences_for_direction(
        self, 
        differences: List[Difference],
        direction: SyncDirection
    ) -> List[Difference]:
        """
        Transform differences based on sync direction.
        
        - SOURCE_TO_TARGET (default): Apply changes to make TARGET look like SOURCE
        - TARGET_TO_SOURCE: Apply changes to make SOURCE look like TARGET (reverse)
        """
        if direction == SyncDirection.SOURCE_TO_TARGET:
            # Default behavior - no transformation needed
            return differences
        
        # TARGET_TO_SOURCE: Reverse the differences
        transformed = []
        for diff in differences:
            # Deep copy to avoid modifying original
            new_diff = copy.deepcopy(diff)
            
            # Reverse diff type if mappable
            if diff.diff_type in REVERSE_DIFF_TYPE_MAP:
                new_diff.diff_type = REVERSE_DIFF_TYPE_MAP[diff.diff_type]
            
            # Swap source and target values
            new_diff.source_value = diff.target_value
            new_diff.target_value = diff.source_value
            
            # Update description to reflect reversed direction
            new_diff.description = self._reverse_description(diff.description)
            
            transformed.append(new_diff)
        
        return transformed
    
    def _reverse_description(self, description: str) -> str:
        """Reverse direction references in description"""
        import re
        
        result = description
        
        # Use placeholder to avoid double replacement
        result = re.sub(
            r'exists only in source', 
            '<<TARGET_PLACEHOLDER>>', 
            result, 
            flags=re.IGNORECASE
        )
        result = re.sub(
            r'exists only in target', 
            'exists only in source', 
            result, 
            flags=re.IGNORECASE
        )
        result = result.replace('<<TARGET_PLACEHOLDER>>', 'exists only in target')
        
        # Same for "missing in" patterns
        result = re.sub(
            r'missing in source', 
            '<<TARGET_PLACEHOLDER2>>', 
            result, 
            flags=re.IGNORECASE
        )
        result = re.sub(
            r'missing in target', 
            'missing in source', 
            result, 
            flags=re.IGNORECASE
        )
        result = result.replace('<<TARGET_PLACEHOLDER2>>', 'missing in target')
        
        return result
        
    def generate_sync_script(self) -> SyncScript:
        """Generate forward and rollback scripts"""
        # Build dependency graph
        self._build_dependency_graph()
        
        # Sort differences by dependencies
        ordered_differences = self._topological_sort()
        
        # Filter out redundant changes for tables that will be dropped or created
        filtered_differences = self._filter_redundant_changes(ordered_differences)
        
        # Generate SQL statements
        forward_statements = []
        rollback_statements = []

        logger.info(f"Generating statements for {len(filtered_differences)} differences")
        for diff in filtered_differences:
            try:
                logger.info(f"Processing: {diff.diff_type.value} - {diff.schema_name}.{diff.object_name}.{diff.sub_object_name or ''}")
                forward, rollback = self._generate_statements(diff)
                if forward:
                    forward_statements.append(forward)
                    logger.info(f"Generated forward statement for {diff.object_name}")
                else:
                    logger.warning(f"No forward statement generated for {diff.diff_type.value} - {diff.object_name}")
                if rollback:
                    rollback_statements.append(rollback)
            except Exception as e:
                logger.warning(f"Failed to generate statement for {diff.object_name}: {e}")
                self.warnings.append(f"Could not generate SQL for {diff.object_name}: {str(e)}")
        
        # Analyze impact
        impact = self._analyze_impact(ordered_differences)
        
        # Determine script title based on direction
        if self.direction == SyncDirection.SOURCE_TO_TARGET:
            forward_title = "Forward Migration (Source → Target)"
            rollback_title = "Rollback Script (Target → Source)"
        else:
            forward_title = "Forward Migration (Target → Source)"
            rollback_title = "Rollback Script (Source → Target)"
        
        return SyncScript(
            comparison_id=self.comparison_id,
            forward_script=self._format_script(forward_statements, forward_title),
            rollback_script=self._format_script(list(reversed(rollback_statements)), rollback_title),
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
    
    def _filter_redundant_changes(self, differences: List[Difference]) -> List[Difference]:
        """Filter out redundant changes for tables that will be dropped or created
        
        If a table is being dropped, we don't need to:
        - Drop/modify columns
        - Drop/modify indexes
        - Drop/modify constraints
        
        If a table is being created, we don't need to:
        - Add columns (they're part of CREATE TABLE)
        - Add indexes (can be added, but CREATE TABLE should include them)
        - Add constraints (can be added, but CREATE TABLE should include them)
        
        Note: This function is called AFTER _transform_differences_for_direction,
        so diff_types have already been transformed based on direction.
        After transformation:
        - TABLE_MISSING_TARGET always means DROP TABLE (regardless of direction)
        - TABLE_MISSING_SOURCE always means CREATE TABLE (regardless of direction)
        """
        # Find tables being dropped or created
        tables_to_drop: set = set()
        tables_to_create: set = set()
        
        for diff in differences:
            if diff.object_type == ObjectType.TABLE:
                table_key = f"{diff.schema_name}.{diff.object_name}"
                # TABLE_MISSING_SOURCE = Source에 없음 = Target에서 DROP
                # TABLE_MISSING_TARGET = Target에 없음 = Target에 CREATE
                if diff.diff_type == DiffType.TABLE_MISSING_SOURCE:
                    tables_to_drop.add(table_key)
                elif diff.diff_type == DiffType.TABLE_MISSING_TARGET:
                    tables_to_create.add(table_key)
        
        if not tables_to_drop:
            return differences
        
        # Log filtered tables
        logger.info(f"Tables to be dropped: {tables_to_drop}")
        
        # Filter out redundant changes
        filtered = []
        skipped_count = 0
        
        for diff in differences:
            table_key = f"{diff.schema_name}.{diff.object_name}"
            
            # Keep table-level changes
            if diff.object_type == ObjectType.TABLE:
                filtered.append(diff)
                continue
            
            # Skip changes for tables that will be dropped
            if table_key in tables_to_drop:
                skipped_count += 1
                logger.debug(f"Skipping {diff.diff_type} for {table_key}.{diff.sub_object_name} (table will be dropped)")
                continue
            
            filtered.append(diff)
        
        if skipped_count > 0:
            self.warnings.append(f"Skipped {skipped_count} changes for tables that will be dropped")
            logger.info(f"Filtered out {skipped_count} redundant changes for tables being dropped")
        
        return filtered
    
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
            DiffType.INDEX_RENAMED: self._gen_rename_index,
            
            # Constraints
            DiffType.CONSTRAINT_MISSING_SOURCE: self._gen_drop_constraint,
            DiffType.CONSTRAINT_MISSING_TARGET: self._gen_create_constraint,
            DiffType.CONSTRAINT_DEFINITION_CHANGED: self._gen_recreate_constraint,
            DiffType.CONSTRAINT_RENAMED: self._gen_rename_constraint,
        }
        
        generator = generators.get(diff.diff_type)
        if generator:
            return generator(diff)
        
        return None, None
    
    # Table generators
    def _gen_create_table(self, diff: Difference) -> Tuple[str, str]:
        """Generate CREATE TABLE statement"""
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        
        # Check if we have table definition in source_value or target_value
        table_data = diff.source_value or diff.target_value
        
        if table_data and isinstance(table_data, dict):
            # Extract table structure
            columns = table_data.get("columns", {})
            engine = table_data.get("engine", "InnoDB")
            collation = table_data.get("collation", "")
            
            if columns and isinstance(columns, dict):
                col_defs = []
                primary_keys = []
                
                # Sort columns by ordinal_position
                sorted_columns = sorted(
                    columns.items(), 
                    key=lambda x: x[1].get("ordinal_position", 0) if isinstance(x[1], dict) else 0
                )
                
                for col_name, col_info in sorted_columns:
                    if isinstance(col_info, dict):
                        col_type = col_info.get("column_type", "VARCHAR(255)")
                        nullable = "NULL" if col_info.get("is_nullable", True) else "NOT NULL"
                        default = ""
                        if col_info.get("column_default") is not None:
                            default_val = col_info.get("column_default")
                            # Quote string defaults, but not expressions like CURRENT_TIMESTAMP
                            if isinstance(default_val, str) and not default_val.upper().startswith(('CURRENT_', 'NULL')):
                                default = f"DEFAULT '{default_val}'"
                            else:
                                default = f"DEFAULT {default_val}"
                        extra = col_info.get("extra", "")
                        if extra and "auto_increment" in extra.lower():
                            extra = "AUTO_INCREMENT"
                        else:
                            extra = ""
                        
                        col_def = f"`{col_name}` {col_type} {nullable} {default} {extra}".strip()
                        # Clean up multiple spaces
                        col_def = " ".join(col_def.split())
                        col_defs.append(col_def)
                        
                        # Track primary keys
                        if col_info.get("column_key") == "PRI":
                            primary_keys.append(f"`{col_name}`")
                
                if col_defs:
                    # Add PRIMARY KEY if exists
                    if primary_keys:
                        col_defs.append(f"PRIMARY KEY ({', '.join(primary_keys)})")
                    
                    # Build CREATE TABLE statement
                    engine_clause = f" ENGINE={engine}" if engine else ""
                    collation_clause = f" COLLATE={collation}" if collation else ""
                    
                    forward = f"CREATE TABLE {table_name} (\n  " + ",\n  ".join(col_defs) + f"\n){engine_clause}{collation_clause};"
                    rollback = f"DROP TABLE IF EXISTS {table_name};"
                    return forward, rollback
        
        # Fallback to TODO comment if we don't have enough info
        forward = f"-- TODO: CREATE TABLE {table_name} (copy structure from source database);"
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
            # Handle both dict and string formats
            if isinstance(diff.target_value, dict):
                col_def = diff.target_value
                column_type = col_def.get("column_type", "VARCHAR(255)")
                nullable = "NULL" if col_def.get("is_nullable", True) else "NOT NULL"
                default_val = col_def.get("column_default")
                default = f"DEFAULT '{default_val}'" if default_val and default_val != "NULL" else ""
                
                forward = f"""-- Add Column: {column_name}
-- Type: {column_type}
-- Nullable: {nullable}
-- Default: {default_val or 'None'}
ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} {nullable} {default};""".strip()
            else:
                # If it's a string, it's likely just the column type
                column_type = str(diff.target_value)
                forward = f"""-- Add Column: {column_name}
-- Type: {column_type}
ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} NULL;"""
            
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
    
    def _build_column_definition(self, col_info: dict, override_type: str = None, override_nullable: bool = None, override_default: str = None) -> str:
        """Build complete column definition preserving all attributes
        
        Args:
            col_info: Column information dict
            override_type: Override column type if specified
            override_nullable: Override nullable if specified (True=NULL, False=NOT NULL)
            override_default: Override default value if specified (use empty string to clear default)
        
        Returns:
            Complete column definition string
        """
        if not isinstance(col_info, dict):
            return str(col_info) if col_info else "VARCHAR(255)"
        
        # Column type
        col_type = override_type if override_type else col_info.get("column_type", "VARCHAR(255)")
        
        # Nullable
        if override_nullable is not None:
            nullable = "NULL" if override_nullable else "NOT NULL"
        else:
            is_nullable = col_info.get("is_nullable", True)
            nullable = "NULL" if is_nullable else "NOT NULL"
        
        # Default value - check for override
        default_clause = ""
        if override_default is not None:
            default_val = override_default
        else:
            default_val = col_info.get("column_default")
        
        if default_val is not None:
            # Handle special cases
            if str(default_val).upper() in ('CURRENT_TIMESTAMP', 'CURRENT_DATE', 'NULL'):
                default_clause = f" DEFAULT {default_val}"
            elif str(default_val).upper().startswith('CURRENT_'):
                default_clause = f" DEFAULT {default_val}"
            else:
                # Quote string values
                default_clause = f" DEFAULT '{default_val}'"
        
        # Extra (AUTO_INCREMENT, ON UPDATE CURRENT_TIMESTAMP, etc.)
        extra_clause = ""
        extra = col_info.get("extra", "")
        if extra:
            extra_clause = f" {extra}"
        
        # Comment - IMPORTANT: MySQL loses comment on MODIFY if not specified
        comment_clause = ""
        comment = col_info.get("comment", "")
        if comment:
            # Escape single quotes in comment
            escaped_comment = comment.replace("'", "''")
            comment_clause = f" COMMENT '{escaped_comment}'"
        
        return f"{col_type} {nullable}{default_clause}{extra_clause}{comment_clause}".strip()
    
    def _gen_alter_column_type(self, diff: Difference) -> Tuple[str, str]:
        """Generate ALTER COLUMN TYPE statement"""
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        column_name = f"`{diff.sub_object_name}`"
        
        # Extract column info
        target_info = diff.target_value if isinstance(diff.target_value, dict) else {}
        source_info = diff.source_value if isinstance(diff.source_value, dict) else {}
        
        target_type = target_info.get("column_type", diff.target_value) if target_info else diff.target_value
        source_type = source_info.get("column_type", diff.source_value) if source_info else diff.source_value
        
        # Build complete column definition with new type but preserving other attributes
        # For forward: use target type but preserve source's other attributes (comment, etc.)
        forward_def = self._build_column_definition(source_info, override_type=target_type) if source_info else target_type
        rollback_def = self._build_column_definition(source_info) if source_info else source_type
        
        forward = f"""-- Modify Column Type: {column_name}
-- From: {source_type}
-- To: {target_type}
-- WARNING: Data conversion may be required
ALTER TABLE {table_name} MODIFY COLUMN {column_name} {forward_def};"""
        
        rollback = f"""-- Rollback Column Type: {column_name}
-- From: {target_type}
-- To: {source_type}
ALTER TABLE {table_name} MODIFY COLUMN {column_name} {rollback_def};"""
        
        return forward, rollback
    
    def _gen_alter_column_default(self, diff: Difference) -> Tuple[str, str]:
        """Generate ALTER COLUMN DEFAULT statement using MODIFY COLUMN (MySQL syntax)"""
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        column_name = f"`{diff.sub_object_name}`"
        
        # Get column info - source_value and target_value could be dict or string
        source_info = diff.source_value if isinstance(diff.source_value, dict) else {}
        target_info = diff.target_value if isinstance(diff.target_value, dict) else {}
        
        # If we have full column info, use _build_column_definition
        if source_info and target_info:
            # Build forward: use target's default with source's other attributes
            forward_def = self._build_column_definition(
                source_info, 
                override_default=target_info.get('column_default')
            )
            # Build rollback: use source's default
            rollback_def = self._build_column_definition(source_info)
            
            target_default = target_info.get('column_default', 'NULL')
            source_default = source_info.get('column_default', 'NULL')
            
            forward = f"""-- Modify Column Default: {column_name}
-- From: {source_default}
-- To: {target_default}
ALTER TABLE {table_name} MODIFY COLUMN {column_name} {forward_def};"""
            
            rollback = f"ALTER TABLE {table_name} MODIFY COLUMN {column_name} {rollback_def};"
        else:
            # Fallback for simple value comparison (legacy format)
            target_default = diff.target_value if diff.target_value else 'NULL'
            source_default = diff.source_value if diff.source_value else 'NULL'

            # Helper function to properly quote default values
            def quote_default(val):
                if val is None or str(val).upper() == 'NULL':
                    return 'NULL'
                val_str = str(val)
                # Don't quote special MySQL expressions
                if val_str.upper() in ('CURRENT_TIMESTAMP', 'CURRENT_DATE', 'NOW()'):
                    return val_str
                if val_str.upper().startswith('CURRENT_'):
                    return val_str
                # Quote string values
                return f"'{val_str}'"

            quoted_target = quote_default(target_default)
            quoted_source = quote_default(source_default)

            # Cannot generate proper MODIFY without full column info
            forward = f"""-- Modify Column Default: {column_name}
-- From: {source_default}
-- To: {target_default}
-- WARNING: Full column definition needed. Using ALTER COLUMN (may not work in MySQL).
ALTER TABLE {table_name} ALTER COLUMN {column_name} SET DEFAULT {quoted_target};"""

            rollback = f"ALTER TABLE {table_name} ALTER COLUMN {column_name} SET DEFAULT {quoted_source};"
        
        return forward, rollback
    
    def _gen_alter_column_nullable(self, diff: Difference) -> Tuple[str, str]:
        """Generate ALTER COLUMN NULL/NOT NULL statement"""
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        column_name = f"`{diff.sub_object_name}`"
        
        # Get column info
        target_info = diff.target_value if isinstance(diff.target_value, dict) else {}
        source_info = diff.source_value if isinstance(diff.source_value, dict) else {}
        
        # Determine the nullable state
        target_is_nullable = target_info.get("is_nullable", True) if target_info else True
        source_is_nullable = source_info.get("is_nullable", True) if source_info else True
        
        target_nullable = "NULL" if target_is_nullable else "NOT NULL"
        source_nullable = "NULL" if source_is_nullable else "NOT NULL"
        
        # Build complete column definition preserving all attributes
        forward_def = self._build_column_definition(source_info, override_nullable=target_is_nullable) if source_info else f"VARCHAR(255) {target_nullable}"
        rollback_def = self._build_column_definition(source_info) if source_info else f"VARCHAR(255) {source_nullable}"
        
        # Generate SQL based on target nullable state
        if not target_is_nullable:
            forward = f"""-- Modify Column Nullable: {column_name}
-- From: {source_nullable}
-- To: {target_nullable}
-- WARNING: Ensure no NULL values exist in column
ALTER TABLE {table_name} MODIFY COLUMN {column_name} {forward_def};"""
        else:
            forward = f"""-- Modify Column Nullable: {column_name}
-- From: {source_nullable}
-- To: {target_nullable}
ALTER TABLE {table_name} MODIFY COLUMN {column_name} {forward_def};"""
        
        rollback = f"ALTER TABLE {table_name} MODIFY COLUMN {column_name} {rollback_def};"
        
        return forward, rollback
    
    # Index generators
    def _gen_create_index(self, diff: Difference) -> Tuple[str, str]:
        """Generate CREATE INDEX statement"""
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        index_name = diff.sub_object_name  # Don't add backticks here, they're added later if needed

        # For INDEX_MISSING_TARGET, the index exists in source, so use source_value
        # For other cases (like after direction transform), use target_value
        idx_data = diff.source_value or diff.target_value

        if idx_data:
            if isinstance(idx_data, dict):
                is_unique = idx_data.get("is_unique")
                columns = idx_data.get("columns", "")
                idx_type = idx_data.get("index_type", "BTREE")
                idx_type_clause = f" USING {idx_type}" if idx_type and idx_type != "BTREE" else ""
                unique_keyword = "UNIQUE " if is_unique else ""
                unique_label = "UNIQUE" if is_unique else "Regular"

                forward = f"""-- Create {unique_label} Index: {index_name}
-- Table: {table_name}
-- Columns: {columns}
-- Type: {idx_type or 'BTREE'}
CREATE {unique_keyword}INDEX `{index_name}` ON {table_name} ({columns}){idx_type_clause};"""
            else:
                # If it's a string, create a basic index
                forward = f"""-- Create Index: {index_name}
-- Table: {table_name}
-- Columns: {idx_data}
CREATE INDEX `{index_name}` ON {table_name} ({idx_data});"""

            rollback = f"DROP INDEX `{index_name}` ON {table_name};"
            return forward, rollback

        return None, None
    
    def _gen_drop_index(self, diff: Difference) -> Tuple[str, str]:
        """Generate DROP INDEX statement"""
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        index_name = diff.sub_object_name  # Don't add backticks here
        
        # Add details about the index being dropped
        if isinstance(diff.source_value, dict):
            idx_data = diff.source_value
            columns = idx_data.get("columns", "")
            idx_type = idx_data.get("index_type", "BTREE")
            unique = "UNIQUE" if idx_data.get("is_unique") else "Regular"
            
            forward = f"""-- Drop {unique} Index: {index_name}
-- Table: {table_name}
-- Columns: {columns}
-- Type: {idx_type}
DROP INDEX `{index_name}` ON {table_name};"""
        else:
            forward = f"""-- Drop Index: {index_name}
-- Table: {table_name}
-- Original definition: {diff.source_value}
DROP INDEX `{index_name}` ON {table_name};"""
        
        rollback = f"-- TODO: RECREATE INDEX `{index_name}` with original definition;"
        
        return forward, rollback
    
    def _gen_rename_index(self, diff: Difference) -> Tuple[str, str]:
        """Generate RENAME INDEX statement (MySQL 5.7+)"""
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        
        source_name = diff.sub_object_name  # Original name in source
        target_name = None
        
        # Get target index name
        if isinstance(diff.target_value, dict):
            target_name = diff.target_value.get("index_name")
        
        if not target_name:
            # Fallback - shouldn't happen
            return None, None
        
        # Determine which way to rename based on direction
        # For SOURCE_TO_TARGET: rename target to match source (target DB is modified)
        # For TARGET_TO_SOURCE: rename source to match target (source DB is modified)
        if self.direction == SyncDirection.SOURCE_TO_TARGET:
            # Target DB should have source's name
            old_name = target_name
            new_name = source_name
            comment = f"Rename index to match source: {old_name} → {new_name}"
        else:
            # Source DB should have target's name
            old_name = source_name
            new_name = target_name
            comment = f"Rename index to match target: {old_name} → {new_name}"
        
        forward = f"""-- {comment}
-- Table: {table_name}
ALTER TABLE {table_name} RENAME INDEX `{old_name}` TO `{new_name}`;"""
        
        rollback = f"ALTER TABLE {table_name} RENAME INDEX `{new_name}` TO `{old_name}`;"
        
        return forward, rollback
    
    def _gen_recreate_index(self, diff: Difference) -> Tuple[str, str]:
        """Generate statements to recreate an index"""
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        index_name = diff.sub_object_name  # Don't add backticks here
        
        # Drop and recreate
        drop_stmt = f"DROP INDEX `{index_name}` ON {table_name};"
        
        if diff.target_value:
            if isinstance(diff.target_value, dict):
                idx_data = diff.target_value
                unique = "UNIQUE" if idx_data.get("is_unique") else ""
                columns = idx_data.get("columns", "")
                idx_type = idx_data.get("index_type", "BTREE")
                idx_type_clause = f"USING {idx_type}" if idx_type != "BTREE" else ""
                
                create_stmt = f"""-- Recreate Index: {index_name}
-- Table: {table_name}
-- Columns: {columns}
-- Type: {idx_type}
CREATE {unique} INDEX `{index_name}` ON {table_name} ({columns}) {idx_type_clause};""".strip()
            else:
                # If it's a string, create a basic index
                create_stmt = f"CREATE INDEX `{index_name}` ON {table_name} ({diff.target_value});"
            
            forward = f"{drop_stmt}\n\n{create_stmt}"
            
            # Rollback would recreate with original definition
            if diff.source_value and isinstance(diff.source_value, dict):
                src_data = diff.source_value
                unique = "UNIQUE" if src_data.get("is_unique") else ""
                columns = src_data.get("columns", "")
                idx_type = src_data.get("index_type", "BTREE")
                idx_type_clause = f"USING {idx_type}" if idx_type != "BTREE" else ""
                rollback = f"DROP INDEX `{index_name}` ON {table_name};\nCREATE {unique} INDEX `{index_name}` ON {table_name} ({columns}) {idx_type_clause};".strip()
            else:
                rollback = f"-- TODO: RECREATE INDEX `{index_name}` WITH ORIGINAL DEFINITION;"
            
            return forward, rollback
        
        return None, None
    
    # Constraint generators
    def _gen_create_constraint(self, diff: Difference) -> Tuple[str, str]:
        """Generate CREATE CONSTRAINT statement"""
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        constraint_name = diff.sub_object_name  # Don't add backticks here

        # For CONSTRAINT_MISSING_TARGET, the constraint exists in source, so use source_value
        const_data = diff.source_value or diff.target_value

        if const_data:
            if isinstance(const_data, dict):
                const_type = const_data.get("constraint_type")
                
                if const_type == "FOREIGN KEY":
                    columns = const_data.get("columns", "")
                    ref_schema = const_data.get("referenced_table_schema", "")
                    ref_table_name = const_data.get("referenced_table_name", "")
                    ref_table = f"`{ref_schema}`.`{ref_table_name}`" if ref_schema and ref_table_name else "UNKNOWN_TABLE"
                    ref_columns = const_data.get("referenced_columns", "")
                    update_rule = const_data.get("update_rule", "RESTRICT")
                    delete_rule = const_data.get("delete_rule", "RESTRICT")
                    
                    forward = f"""-- Add Foreign Key Constraint: {constraint_name}
-- References: {ref_schema}.{ref_table_name} ({ref_columns})
-- Rules: ON UPDATE {update_rule}, ON DELETE {delete_rule}
ALTER TABLE {table_name} 
ADD CONSTRAINT {constraint_name} 
FOREIGN KEY ({columns}) 
REFERENCES {ref_table} ({ref_columns})
ON UPDATE {update_rule} ON DELETE {delete_rule};"""
                    
                elif const_type == "PRIMARY KEY":
                    columns = const_data.get("columns", "")
                    forward = f"""-- Add Primary Key Constraint
-- Columns: {columns}
ALTER TABLE {table_name} ADD PRIMARY KEY ({columns});"""
                    
                elif const_type == "UNIQUE":
                    columns = const_data.get("columns", "")
                    forward = f"""-- Add Unique Constraint: {constraint_name}
-- Columns: {columns}
ALTER TABLE {table_name} ADD CONSTRAINT {constraint_name} UNIQUE ({columns});"""
                    
                else:
                    forward = f"-- TODO: ADD {const_type} CONSTRAINT {constraint_name};"
                    
            else:
                # Handle string format
                forward = f"-- Add constraint: {constraint_name}\n-- Definition: {const_data}\n-- TODO: Complete constraint definition;"

            # Generate appropriate rollback based on constraint type
            if isinstance(const_data, dict):
                rollback_const_type = const_data.get("constraint_type", "")
                if rollback_const_type == "PRIMARY KEY":
                    rollback = f"ALTER TABLE {table_name} DROP PRIMARY KEY;"
                elif rollback_const_type == "FOREIGN KEY":
                    rollback = f"ALTER TABLE {table_name} DROP FOREIGN KEY {constraint_name};"
                elif rollback_const_type == "UNIQUE":
                    rollback = f"ALTER TABLE {table_name} DROP INDEX {constraint_name};"
                else:
                    rollback = f"-- TODO: DROP CONSTRAINT {constraint_name};"
            else:
                # Guess based on string content
                if "PRIMARY" in str(const_data):
                    rollback = f"ALTER TABLE {table_name} DROP PRIMARY KEY;"
                elif "FOREIGN" in str(const_data):
                    rollback = f"ALTER TABLE {table_name} DROP FOREIGN KEY {constraint_name};"
                else:
                    rollback = f"ALTER TABLE {table_name} DROP INDEX {constraint_name};"

            return forward.strip(), rollback
        
        return None, None
    
    def _gen_drop_constraint(self, diff: Difference) -> Tuple[str, str]:
        """Generate DROP CONSTRAINT statement"""
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        constraint_name = f"`{diff.sub_object_name}`"
        
        # Generate appropriate drop statement based on constraint type
        if isinstance(diff.source_value, dict):
            const_type = diff.source_value.get("constraint_type", "")
            if const_type == "PRIMARY KEY":
                forward = f"-- Drop Primary Key\nALTER TABLE {table_name} DROP PRIMARY KEY;"
                rollback = f"-- TODO: RECREATE PRIMARY KEY with original definition"
            elif const_type == "FOREIGN KEY":
                columns = diff.source_value.get("columns", "")
                ref_table = diff.source_value.get("referenced_table_name", "")
                ref_columns = diff.source_value.get("referenced_columns", "")
                forward = f"-- Drop Foreign Key: {constraint_name} ({columns}) -> {ref_table}({ref_columns})\nALTER TABLE {table_name} DROP FOREIGN KEY {constraint_name};"
                rollback = f"-- TODO: RECREATE FOREIGN KEY {constraint_name}"
            elif const_type == "UNIQUE":
                columns = diff.source_value.get("columns", "")
                forward = f"-- Drop Unique Constraint: {constraint_name} ({columns})\nALTER TABLE {table_name} DROP INDEX {constraint_name};"
                rollback = f"-- TODO: RECREATE UNIQUE CONSTRAINT {constraint_name}"
            else:
                forward = f"-- Drop {const_type} constraint: {constraint_name}\nALTER TABLE {table_name} DROP CONSTRAINT {constraint_name};"
                rollback = f"-- TODO: RECREATE CONSTRAINT {constraint_name};"
        else:
            # Fallback for string format
            forward = f"-- Drop constraint: {constraint_name}\n-- Original definition: {diff.source_value}\nALTER TABLE {table_name} DROP CONSTRAINT {constraint_name};"
            rollback = f"-- TODO: RECREATE CONSTRAINT {constraint_name};"
        
        return forward, rollback
    
    def _gen_recreate_constraint(self, diff: Difference) -> Tuple[str, str]:
        """Generate statements to recreate a constraint"""
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        constraint_name = diff.sub_object_name  # Don't add backticks here
        
        # First drop the old constraint
        drop_stmt, _ = self._gen_drop_constraint(diff)
        
        # Then create the new one
        create_stmt, rollback_stmt = self._gen_create_constraint(diff)
        
        if drop_stmt and create_stmt:
            forward = f"{drop_stmt}\n\n{create_stmt}"
            # For rollback, we'd need to recreate the original
            if isinstance(diff.source_value, dict):
                # Create a temporary diff for the original constraint
                original_diff = Difference(
                    diff_type=diff.diff_type,
                    severity=diff.severity,
                    object_type=diff.object_type,
                    schema_name=diff.schema_name,
                    object_name=diff.object_name,
                    sub_object_name=diff.sub_object_name,
                    source_value=None,
                    target_value=diff.source_value,  # Use source as target for rollback
                    description=diff.description
                )
                rollback_create, _ = self._gen_create_constraint(original_diff)
                rollback = f"-- Drop modified constraint\nALTER TABLE {table_name} DROP CONSTRAINT {constraint_name};\n\n{rollback_create}"
            else:
                rollback = f"-- TODO: RECREATE CONSTRAINT {constraint_name} WITH ORIGINAL DEFINITION"
            
            return forward, rollback
        
        return None, None
    
    def _gen_rename_constraint(self, diff: Difference) -> Tuple[str, str]:
        """Generate RENAME constraint statement
        
        Note: MySQL doesn't support directly renaming constraints.
        - UNIQUE constraints are actually indexes, so use RENAME INDEX
        - FOREIGN KEY must be dropped and recreated
        """
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        
        source_name = diff.sub_object_name
        target_name = None
        constraint_type = None
        
        if isinstance(diff.target_value, dict):
            target_name = diff.target_value.get("constraint_name")
            constraint_type = diff.target_value.get("constraint_type")
        
        if not target_name:
            return None, None
        
        # Determine which way to rename based on direction
        if self.direction == SyncDirection.SOURCE_TO_TARGET:
            old_name = target_name
            new_name = source_name
        else:
            old_name = source_name
            new_name = target_name
        
        # UNIQUE constraints are actually indexes in MySQL
        if constraint_type == "UNIQUE":
            forward = f"""-- Rename UNIQUE constraint (implemented as index)
-- {old_name} → {new_name}
-- Table: {table_name}
ALTER TABLE {table_name} RENAME INDEX `{old_name}` TO `{new_name}`;"""
            rollback = f"ALTER TABLE {table_name} RENAME INDEX `{new_name}` TO `{old_name}`;"
            return forward, rollback
        
        # FOREIGN KEY must be dropped and recreated
        elif constraint_type == "FOREIGN KEY":
            const_data = diff.source_value if self.direction == SyncDirection.TARGET_TO_SOURCE else diff.target_value
            if isinstance(const_data, dict):
                columns = const_data.get("columns", "")
                ref_schema = const_data.get("referenced_table_schema", "")
                ref_table = const_data.get("referenced_table_name", "")
                ref_columns = const_data.get("referenced_columns", "")
                update_rule = const_data.get("update_rule", "RESTRICT")
                delete_rule = const_data.get("delete_rule", "RESTRICT")
                
                forward = f"""-- Rename FOREIGN KEY constraint (drop and recreate)
-- {old_name} → {new_name}
-- Table: {table_name}
ALTER TABLE {table_name} DROP FOREIGN KEY `{old_name}`;
ALTER TABLE {table_name} ADD CONSTRAINT `{new_name}` FOREIGN KEY ({columns}) 
    REFERENCES `{ref_schema}`.`{ref_table}` ({ref_columns}) 
    ON UPDATE {update_rule} ON DELETE {delete_rule};"""
                
                rollback = f"""ALTER TABLE {table_name} DROP FOREIGN KEY `{new_name}`;
ALTER TABLE {table_name} ADD CONSTRAINT `{old_name}` FOREIGN KEY ({columns}) 
    REFERENCES `{ref_schema}`.`{ref_table}` ({ref_columns}) 
    ON UPDATE {update_rule} ON DELETE {delete_rule};"""
                return forward, rollback
        
        # Other constraints - generic drop and recreate
        forward = f"""-- Rename constraint (drop and recreate)
-- {old_name} → {new_name}
ALTER TABLE {table_name} DROP CONSTRAINT `{old_name}`;
-- TODO: Add constraint with new name `{new_name}`;"""
        rollback = f"-- TODO: Reverse constraint rename"
        
        return forward, rollback
    
    def _format_script(self, statements: List[str], title: str) -> str:
        """Format SQL script with header and sections"""
        direction_desc = (
            "Making TARGET database match SOURCE" 
            if self.direction == SyncDirection.SOURCE_TO_TARGET 
            else "Making SOURCE database match TARGET"
        )
        
        script = f"""-- {title}
-- Generated by Schema Diff Pro
-- Comparison ID: {self.comparison_id}
-- Direction: {self.direction.value}
-- Description: {direction_desc}
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
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
    DiffType.COLUMN_RENAMED: DiffType.COLUMN_RENAMED,  # Same in both directions, just swap names
    # Indexes
    DiffType.INDEX_MISSING_SOURCE: DiffType.INDEX_MISSING_TARGET,
    DiffType.INDEX_MISSING_TARGET: DiffType.INDEX_MISSING_SOURCE,
    DiffType.INDEX_RENAMED: DiffType.INDEX_RENAMED,  # Same in both directions, just swap names
    # Constraints
    DiffType.CONSTRAINT_MISSING_SOURCE: DiffType.CONSTRAINT_MISSING_TARGET,
    DiffType.CONSTRAINT_MISSING_TARGET: DiffType.CONSTRAINT_MISSING_SOURCE,
    DiffType.CONSTRAINT_RENAMED: DiffType.CONSTRAINT_RENAMED,  # Same in both directions, just swap names
    # Partitions
    DiffType.PARTITION_MISSING_SOURCE: DiffType.PARTITION_MISSING_TARGET,
    DiffType.PARTITION_MISSING_TARGET: DiffType.PARTITION_MISSING_SOURCE,
    DiffType.PARTITION_DEFINITION_CHANGED: DiffType.PARTITION_DEFINITION_CHANGED,
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
            DiffType.TABLE_MISSING_TARGET: self._gen_create_or_alter_table,
            
            # Columns
            DiffType.COLUMN_ADDED: self._gen_add_column,
            DiffType.COLUMN_REMOVED: self._gen_drop_column,
            DiffType.COLUMN_RENAMED: self._gen_rename_column,
            DiffType.COLUMN_TYPE_CHANGED: self._gen_alter_column_type,
            DiffType.COLUMN_DEFAULT_CHANGED: self._gen_alter_column_default,
            DiffType.COLUMN_NULLABLE_CHANGED: self._gen_alter_column_nullable,
            DiffType.COLUMN_EXTRA_CHANGED: self._gen_alter_column_extra,
            
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

            # Partitions
            DiffType.PARTITION_MISSING_SOURCE: self._gen_partition_missing_source,
            DiffType.PARTITION_MISSING_TARGET: self._gen_partition_missing_target,
            DiffType.PARTITION_DEFINITION_CHANGED: self._gen_partition_definition_changed,
        }
        
        generator = generators.get(diff.diff_type)
        if generator:
            return generator(diff)
        
        return None, None
    
    # Table generators
    def _gen_create_or_alter_table(self, diff: Difference) -> Tuple[str, str]:
        """Generate CREATE TABLE or ALTER TABLE statement based on sub_object_name"""
        # If sub_object_name is set, it's a table property change (engine, comment, collation)
        if diff.sub_object_name:
            return self._gen_alter_table_property(diff)
        else:
            return self._gen_create_table(diff)
    
    def _gen_alter_table_property(self, diff: Difference) -> Tuple[str, str]:
        """Generate ALTER TABLE statement for table properties (engine, comment, collation)"""
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        property_name = diff.sub_object_name
        source_value = diff.source_value
        target_value = diff.target_value
        
        if property_name == "engine":
            forward = f"""-- Modify Table Engine: {table_name}
-- From: {source_value}
-- To: {target_value}
ALTER TABLE {table_name} ENGINE={target_value};"""
            rollback = f"ALTER TABLE {table_name} ENGINE={source_value};"
            
        elif property_name == "comment":
            # Escape single quotes in comments
            escaped_target = str(target_value or "").replace("'", "''")
            escaped_source = str(source_value or "").replace("'", "''")
            
            forward = f"""-- Modify Table Comment: {table_name}
-- From: {source_value or '(none)'}
-- To: {target_value or '(none)'}
ALTER TABLE {table_name} COMMENT='{escaped_target}';"""
            rollback = f"ALTER TABLE {table_name} COMMENT='{escaped_source}';"
            
        elif property_name == "collation":
            forward = f"""-- Modify Table Collation: {table_name}
-- From: {source_value}
-- To: {target_value}
ALTER TABLE {table_name} COLLATE={target_value};"""
            rollback = f"ALTER TABLE {table_name} COLLATE={source_value};"
            
        else:
            # Unknown property
            forward = f"""-- Modify Table Property '{property_name}': {table_name}
-- From: {source_value}
-- To: {target_value}
-- TODO: Implement ALTER TABLE for {property_name};"""
            rollback = f"-- TODO: Rollback table property {property_name};"
        
        return forward, rollback
    
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
                        
                        # Add comment, charset, collation
                        comment = col_info.get("comment", "")
                        comment_clause = ""
                        if comment:
                            escaped_comment = str(comment).replace("'", "''")
                            comment_clause = f"COMMENT '{escaped_comment}'"
                        
                        charset = col_info.get("character_set", "")
                        charset_clause = f"CHARACTER SET {charset}" if charset else ""
                        
                        collation = col_info.get("collation", "")
                        collation_clause = f"COLLATE {collation}" if collation else ""
                        
                        col_def = f"`{col_name}` {col_type} {charset_clause} {collation_clause} {nullable} {default} {extra} {comment_clause}".strip()
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
                    
                    # Add table comment if exists
                    comment = table_data.get("comment", "")
                    comment_clause = ""
                    if comment:
                        escaped_comment = str(comment).replace("'", "''")
                        comment_clause = f" COMMENT='{escaped_comment}'"
                    
                    forward = f"CREATE TABLE {table_name} (\n  " + ",\n  ".join(col_defs) + f"\n){engine_clause}{collation_clause}{comment_clause};"
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
        """Generate ADD COLUMN statement
        COLUMN_ADDED means column exists ONLY in target, not in source.
        Forward: Make target like source = DROP this column from target
        """
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        column_name = f"`{diff.sub_object_name}`"
        
        # COLUMN_ADDED: target has it, source doesn't
        # Forward: DROP from target (to match source)
        # Rollback: ADD back to target
        
        if diff.target_value:
            # Build rollback statement with full column info
            if isinstance(diff.target_value, dict):
                col_def = diff.target_value
                column_definition = self._build_column_definition(col_def)
                
                column_type = col_def.get("column_type", "VARCHAR(255)")
                nullable = "NULL" if col_def.get("is_nullable", True) else "NOT NULL"
                default_val = col_def.get("column_default")
                comment = col_def.get("comment")
                
                # Build detailed comment for rollback
                details = [f"Type: {column_type}", f"Nullable: {nullable}"]
                if default_val:
                    details.append(f"Default: {default_val}")
                if comment:
                    details.append(f"Comment: {comment}")

                # Determine column position (AFTER or FIRST)
                after_column = col_def.get("after_column")
                position_clause = ""
                if after_column:
                    position_clause = f" AFTER `{after_column}`"
                elif col_def.get("ordinal_position") == 1:
                    position_clause = " FIRST"

                rollback = f"""-- Re-add Column: {column_name}
-- {', '.join(details)}
ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}{position_clause};"""
            else:
                column_type = str(diff.target_value)
                rollback = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} NULL;"
            
            forward = f"""-- Drop Column (exists only in target, not in source): {column_name}
ALTER TABLE {table_name} DROP COLUMN {column_name};"""
            
            self.warnings.append(f"Dropping column {table_name}.{column_name} - data will be lost!")
            
            return forward, rollback
        
        return None, None
    
    def _gen_drop_column(self, diff: Difference) -> Tuple[str, str]:
        """Generate DROP COLUMN statement
        COLUMN_REMOVED means column exists ONLY in source, not in target.
        Forward: Make target like source = ADD this column to target
        """
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        column_name = f"`{diff.sub_object_name}`"
        
        # COLUMN_REMOVED: source has it, target doesn't
        # Forward: ADD to target (to match source)
        # Rollback: DROP from target
        
        if diff.source_value:
            # Build forward statement with full column info
            if isinstance(diff.source_value, dict):
                col_def = diff.source_value
                column_definition = self._build_column_definition(col_def)
                
                column_type = col_def.get("column_type", "VARCHAR(255)")
                nullable = "NULL" if col_def.get("is_nullable", True) else "NOT NULL"
                default_val = col_def.get("column_default")
                comment = col_def.get("comment")
                charset = col_def.get("character_set")
                collation = col_def.get("collation")
                
                # Build detailed comment
                details = [f"Type: {column_type}", f"Nullable: {nullable}"]
                if default_val:
                    details.append(f"Default: {default_val}")
                if comment:
                    details.append(f"Comment: {comment}")
                if charset:
                    details.append(f"Charset: {charset}")
                if collation:
                    details.append(f"Collation: {collation}")
                
                # Determine column position (AFTER or FIRST)
                after_column = col_def.get("after_column")
                position_clause = ""
                if after_column:
                    position_clause = f" AFTER `{after_column}`"
                elif col_def.get("ordinal_position") == 1:
                    position_clause = " FIRST"

                forward = f"""-- Add Column (exists only in source, not in target): {column_name}
-- {', '.join(details)}
ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}{position_clause};"""
            else:
                column_type = str(diff.source_value)
                forward = f"""-- Add Column: {column_name}
-- Type: {column_type}
ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} NULL;"""
            
            rollback = f"""-- Drop Column: {column_name}
ALTER TABLE {table_name} DROP COLUMN {column_name};"""

            return forward, rollback

        return None, None

    def _gen_rename_column(self, diff: Difference) -> Tuple[str, str]:
        """Generate CHANGE COLUMN statement for column rename

        MySQL syntax: ALTER TABLE table_name CHANGE COLUMN old_name new_name column_definition;

        diff.sub_object_name = source column name (what we want to rename TO)
        diff.source_display_value = source column name (desired name)
        diff.target_display_value = target column name (current name)
        diff.source_value = source column info (full definition for the new name)
        diff.target_value = target column info (full definition for the current name)
        """
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"

        # source_display_value = what we want (source column name)
        # target_display_value = current state (target column name)
        new_name = diff.source_display_value or diff.sub_object_name
        old_name = diff.target_display_value

        if not old_name or not new_name:
            return None, None

        # Build column definition from source (what we want it to become)
        source_info = diff.source_value if isinstance(diff.source_value, dict) else {}
        column_definition = self._build_column_definition(source_info) if source_info else "VARCHAR(255)"

        # Build rollback definition from target (what it was)
        target_info = diff.target_value if isinstance(diff.target_value, dict) else {}
        rollback_definition = self._build_column_definition(target_info) if target_info else "VARCHAR(255)"

        forward = f"""-- Rename Column: {old_name} → {new_name}
-- Table: {table_name}
ALTER TABLE {table_name} CHANGE COLUMN `{old_name}` `{new_name}` {column_definition};"""

        rollback = f"""-- Rollback Column Rename: {new_name} → {old_name}
ALTER TABLE {table_name} CHANGE COLUMN `{new_name}` `{old_name}` {rollback_definition};"""

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
        
        # Character set (for text-based columns)
        charset = col_info.get("character_set", "")
        charset_clause = f" CHARACTER SET {charset}" if charset else ""
        
        # Collation (for text-based columns)
        collation = col_info.get("collation", "")
        collation_clause = f" COLLATE {collation}" if collation else ""
        
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
            # Handle special cases (MySQL expressions that should not be quoted)
            default_str = str(default_val)
            default_upper = default_str.upper()
            if default_upper in ('CURRENT_TIMESTAMP', 'CURRENT_DATE', 'NULL', 'TRUE', 'FALSE'):
                default_clause = f" DEFAULT {default_val}"
            elif default_upper.startswith('CURRENT_') or default_upper.startswith('NOW('):
                default_clause = f" DEFAULT {default_val}"
            else:
                # Quote string values with proper escaping to prevent SQL injection
                escaped_val = default_str.replace("\\", "\\\\").replace("'", "''")
                default_clause = f" DEFAULT '{escaped_val}'"
        
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
        
        return f"{col_type}{charset_clause}{collation_clause} {nullable}{default_clause}{extra_clause}{comment_clause}".strip()
    
    def _gen_alter_column_type(self, diff: Difference) -> Tuple[str, str]:
        """Generate ALTER COLUMN TYPE statement"""
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        column_name = f"`{diff.sub_object_name}`"
        
        # Extract column info
        target_info = diff.target_value if isinstance(diff.target_value, dict) else {}
        source_info = diff.source_value if isinstance(diff.source_value, dict) else {}
        
        target_type = target_info.get("column_type", diff.target_value) if target_info else diff.target_value
        source_type = source_info.get("column_type", diff.source_value) if source_info else diff.source_value
        
        # Build complete column definition
        # Forward: Make target look like source (use source's complete definition)
        forward_def = self._build_column_definition(source_info) if source_info else source_type
        # Rollback: Restore target's original definition
        rollback_def = self._build_column_definition(target_info) if target_info else target_type
        
        forward = f"""-- Modify Column Type: {column_name}
-- From: {target_type}
-- To: {source_type}
-- WARNING: Data conversion may be required
ALTER TABLE {table_name} MODIFY COLUMN {column_name} {forward_def};"""
        
        rollback = f"""-- Rollback Column Type: {column_name}
-- From: {source_type}
-- To: {target_type}
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
            # Forward: Make target look like source (use source's complete definition)
            forward_def = self._build_column_definition(source_info)
            # Rollback: Restore target's original definition
            rollback_def = self._build_column_definition(target_info)
            
            target_default = target_info.get('column_default', 'NULL')
            source_default = source_info.get('column_default', 'NULL')
            
            forward = f"""-- Modify Column Default: {column_name}
-- From: {target_default}
-- To: {source_default}
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

            quoted_source = quote_default(source_default)
            quoted_target = quote_default(target_default)

            # Cannot generate proper MODIFY without full column info
            forward = f"""-- Modify Column Default: {column_name}
-- From: {target_default}
-- To: {source_default}
-- WARNING: Full column definition needed. Using ALTER COLUMN (may not work in MySQL).
ALTER TABLE {table_name} ALTER COLUMN {column_name} SET DEFAULT {quoted_source};"""

            rollback = f"ALTER TABLE {table_name} ALTER COLUMN {column_name} SET DEFAULT {quoted_target};"
        
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
        
        # Build complete column definition
        # Forward: Make target look like source (use source's complete definition)
        forward_def = self._build_column_definition(source_info) if source_info else f"VARCHAR(255) {source_nullable}"
        # Rollback: Restore target's original definition
        rollback_def = self._build_column_definition(target_info) if target_info else f"VARCHAR(255) {target_nullable}"
        
        # Generate SQL based on source nullable state (what we're changing TO)
        if not source_is_nullable:
            forward = f"""-- Modify Column Nullable: {column_name}
-- From: {target_nullable}
-- To: {source_nullable}
-- WARNING: Ensure no NULL values exist in column
ALTER TABLE {table_name} MODIFY COLUMN {column_name} {forward_def};"""
        else:
            forward = f"""-- Modify Column Nullable: {column_name}
-- From: {target_nullable}
-- To: {source_nullable}
ALTER TABLE {table_name} MODIFY COLUMN {column_name} {forward_def};"""
        
        rollback = f"ALTER TABLE {table_name} MODIFY COLUMN {column_name} {rollback_def};"
        
        return forward, rollback
    
    def _gen_alter_column_extra(self, diff: Difference) -> Tuple[str, str]:
        """Generate ALTER COLUMN statement for extra properties (comment, charset, collation, etc.)"""
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        column_name = f"`{diff.sub_object_name}`"
        
        # Get column info
        target_info = diff.target_value if isinstance(diff.target_value, dict) else {}
        source_info = diff.source_value if isinstance(diff.source_value, dict) else {}
        
        if not source_info or not target_info:
            return None, None
        
        # Forward: Make target look like source (apply source's properties to target)
        # We need to use target's base structure but override with source's changed property
        forward_def = self._build_column_definition(source_info)
        # Rollback: Restore target's original properties
        rollback_def = self._build_column_definition(target_info)
        
        # Determine what changed based on description
        description = diff.description.lower()
        if "comment" in description:
            change_type = "comment"
            source_val = source_info.get("comment") or "(none)"
            target_val = target_info.get("comment") or "(none)"
        elif "charset" in description or "character set" in description:
            change_type = "character set"
            source_val = source_info.get("character_set") or "(none)"
            target_val = target_info.get("character_set") or "(none)"
        elif "collation" in description:
            change_type = "collation"
            source_val = source_info.get("collation") or "(none)"
            target_val = target_info.get("collation") or "(none)"
        else:
            change_type = "extra properties"
            source_val = source_info.get("extra") or "(none)"
            target_val = target_info.get("extra") or "(none)"
        
        forward = f"""-- Modify Column {change_type.title()}: {column_name}
-- From: {target_val}
-- To: {source_val}
ALTER TABLE {table_name} MODIFY COLUMN {column_name} {forward_def};"""
        
        rollback = f"""-- Rollback Column {change_type.title()}: {column_name}
ALTER TABLE {table_name} MODIFY COLUMN {column_name} {rollback_def};"""
        
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

    # Partition generators
    def _gen_partition_missing_target(self, diff: Difference) -> Tuple[str, str]:
        """Generate SQL for partition missing in target (add partition)"""
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        part_name = diff.sub_object_name

        # Handle case of all partitions missing (table not partitioned in target)
        if part_name == "(all partitions)":
            source_info = diff.source_value
            if source_info and isinstance(source_info, dict):
                method = source_info.get("partition_method", "RANGE")
                expression = source_info.get("partition_expression", "")
                partitions = source_info.get("partitions", {})

                if partitions:
                    part_defs = []
                    for pname, pinfo in sorted(partitions.items(), key=lambda x: x[1].get("ordinal_position", 0)):
                        desc = pinfo.get("description", "")
                        if method == "LIST":
                            part_defs.append(f"PARTITION `{pname}` VALUES IN {desc}")
                        else:
                            part_defs.append(f"PARTITION `{pname}` VALUES LESS THAN ({desc})")

                    forward = f"""-- Add partitioning to table (requires data reorganization)
-- Table: {table_name}
-- Method: {method}
-- Expression: {expression}
-- WARNING: This requires recreating the table with partitions
-- Consider using pt-online-schema-change for large tables
ALTER TABLE {table_name}
PARTITION BY {method} ({expression}) (
  {','.join(part_defs)}
);"""
                    rollback = f"""-- Remove partitioning from table
ALTER TABLE {table_name} REMOVE PARTITIONING;"""
                    self.warnings.append(f"Adding partitions to {table_name} may require data reorganization")
                    return forward, rollback

            return f"-- Cannot add partitioning: insufficient information for {table_name}", ""

        # Handle case of single partition missing
        partition_info = diff.source_value
        if not partition_info or not isinstance(partition_info, dict):
            return f"-- Unable to generate ADD PARTITION for {part_name}", ""

        part_desc = partition_info.get("description", "")

        # Determine partition type from description
        if "MAXVALUE" in str(part_desc).upper() or (part_desc and not str(part_desc).startswith("(")):
            # RANGE partition: VALUES LESS THAN
            forward = f"""-- Add partition to table
-- Table: {table_name}
-- Partition: {part_name}
ALTER TABLE {table_name} ADD PARTITION (PARTITION `{part_name}` VALUES LESS THAN ({part_desc}));"""
        else:
            # LIST partition: VALUES IN
            forward = f"""-- Add partition to table
-- Table: {table_name}
-- Partition: {part_name}
ALTER TABLE {table_name} ADD PARTITION (PARTITION `{part_name}` VALUES IN {part_desc});"""

        rollback = f"""-- Drop partition from table
-- WARNING: This will DELETE all data in the partition!
ALTER TABLE {table_name} DROP PARTITION `{part_name}`;"""

        return forward, rollback

    def _gen_partition_missing_source(self, diff: Difference) -> Tuple[str, str]:
        """Generate SQL for partition missing in source (drop partition)"""
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        part_name = diff.sub_object_name

        # Handle case of all partitions missing in source (table should not be partitioned)
        if part_name == "(all partitions)":
            forward = f"""-- Remove partitioning from table
-- Table: {table_name}
-- WARNING: This will merge all partition data into a single table
ALTER TABLE {table_name} REMOVE PARTITIONING;"""

            target_info = diff.target_value
            if target_info and isinstance(target_info, dict):
                method = target_info.get("partition_method", "RANGE")
                expression = target_info.get("partition_expression", "")
                partitions = target_info.get("partitions", {})

                if partitions:
                    part_defs = []
                    for pname, pinfo in sorted(partitions.items(), key=lambda x: x[1].get("ordinal_position", 0)):
                        desc = pinfo.get("description", "")
                        if method == "LIST":
                            part_defs.append(f"PARTITION `{pname}` VALUES IN {desc}")
                        else:
                            part_defs.append(f"PARTITION `{pname}` VALUES LESS THAN ({desc})")

                    rollback = f"""-- Re-add partitioning to table
ALTER TABLE {table_name}
PARTITION BY {method} ({expression}) (
  {','.join(part_defs)}
);"""
                else:
                    rollback = f"-- TODO: Re-add partitioning to {table_name}"
            else:
                rollback = f"-- TODO: Re-add partitioning to {table_name}"

            self.warnings.append(f"Removing partitions from {table_name} - ensure data is backed up!")
            return forward, rollback

        # Handle case of single partition to drop
        partition_info = diff.target_value

        forward = f"""-- Drop partition from table
-- Table: {table_name}
-- Partition: {part_name}
-- WARNING: This will DELETE all data in the partition!
ALTER TABLE {table_name} DROP PARTITION `{part_name}`;"""

        # Rollback needs partition definition
        if partition_info and isinstance(partition_info, dict):
            part_desc = partition_info.get("description", "")
            if "MAXVALUE" in str(part_desc).upper() or (part_desc and not str(part_desc).startswith("(")):
                rollback = f"ALTER TABLE {table_name} ADD PARTITION (PARTITION `{part_name}` VALUES LESS THAN ({part_desc}));"
            else:
                rollback = f"ALTER TABLE {table_name} ADD PARTITION (PARTITION `{part_name}` VALUES IN {part_desc});"
        else:
            rollback = f"-- TODO: Recreate partition `{part_name}` with original definition"

        self.warnings.append(f"Dropping partition {part_name} from {table_name} - data will be lost!")
        return forward, rollback

    def _gen_partition_definition_changed(self, diff: Difference) -> Tuple[str, str]:
        """Generate SQL for partition definition change (requires REORGANIZE)"""
        table_name = f"`{diff.schema_name}`.`{diff.object_name}`"
        part_name = diff.sub_object_name

        # Handle partition method or expression change
        if part_name in ("partition_method", "partition_expression"):
            forward = f"""-- Partition {part_name} changed
-- Table: {table_name}
-- From: {diff.target_value}
-- To: {diff.source_value}
-- WARNING: Changing {part_name} requires recreating the table
-- This cannot be done with ALTER TABLE - requires export/import or pt-online-schema-change
-- TODO: Implement table recreation with new partitioning scheme"""
            rollback = f"-- Reverse the {part_name} change (requires table recreation)"
            self.warnings.append(f"Changing {part_name} for {table_name} requires table rebuild")
            return forward, rollback

        # Handle individual partition value change
        source_info = diff.source_value
        target_info = diff.target_value

        if source_info and isinstance(source_info, dict):
            source_desc = source_info.get("description", "")
            target_desc = target_info.get("description", "") if isinstance(target_info, dict) else ""

            forward = f"""-- Partition definition changed. Manual REORGANIZE PARTITION required.
-- Table: {table_name}
-- Partition: {part_name}
-- From: {target_desc}
-- To: {source_desc}
-- WARNING: REORGANIZE PARTITION may cause data movement
-- ALTER TABLE {table_name} REORGANIZE PARTITION `{part_name}` INTO (
--   PARTITION `{part_name}` VALUES LESS THAN ({source_desc})
-- );"""
            rollback = f"""-- Reverse the partition reorganization
-- ALTER TABLE {table_name} REORGANIZE PARTITION `{part_name}` INTO (
--   PARTITION `{part_name}` VALUES LESS THAN ({target_desc})
-- );"""
        else:
            forward = f"-- Partition definition changed for {part_name}. Manual intervention required."
            rollback = f"-- Reverse the partition change for {part_name}"

        self.warnings.append(f"Partition {part_name} definition changed - requires REORGANIZE PARTITION")
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
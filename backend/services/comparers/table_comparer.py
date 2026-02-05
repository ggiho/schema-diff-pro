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


class TableComparer(BaseComparer):
    """Compare table structures including columns"""
    
    object_type = ObjectType.TABLE
    
    async def discover_objects(self, connection: DatabaseConnection) -> Dict[str, Any]:
        """Discover all tables and their columns using chunked queries for reliability"""
        try:
            # First, discover tables only (smaller, faster query)
            tables_query = text("""
            SELECT 
                TABLE_SCHEMA,
                TABLE_NAME,
                ENGINE,
                TABLE_COLLATION,
                TABLE_COMMENT,
                CREATE_OPTIONS
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA NOT IN :system_dbs
                AND TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_SCHEMA, TABLE_NAME
            """)
            
            logger.debug("Discovering tables...")
            table_results = await connection.execute_query(
                tables_query,
                {"system_dbs": tuple(settings.SYSTEM_DATABASES)}
            )
            
            tables = {}
            table_list = []
            
            # Process table results and build table structure
            for row in table_results:
                schema_name = row[0]
                table_name = row[1]
                
                # Skip if filtered out
                if not self.should_compare_object(schema_name, table_name):
                    continue
                
                table_key = f"{schema_name}.{table_name}"
                table_list.append((schema_name, table_name))
                
                tables[table_key] = {
                    "schema_name": schema_name,
                    "table_name": table_name,
                    "engine": row[2],
                    "collation": row[3],
                    "comment": row[4],
                    "create_options": row[5],
                    "columns": {}
                }
            
            logger.debug(f"Found {len(table_list)} tables, discovering columns...")
            
            # Now discover columns with micro-batching for SSH tunnel stability
            batch_size = 2 if "127.0.0.1" in str(connection.connection_url) or "localhost" in str(connection.connection_url) else 5  # Ultra-small batches for SSH tunnels
            for i in range(0, len(table_list), batch_size):
                batch = table_list[i:i + batch_size]
                
                # Create WHERE clause for this batch
                table_conditions = []
                for schema_name, table_name in batch:
                    table_conditions.append(f"(c.TABLE_SCHEMA = '{schema_name}' AND c.TABLE_NAME = '{table_name}')")
                
                if not table_conditions:
                    continue
                
                batch_where = " OR ".join(table_conditions)
                
                columns_query = text(f"""
                SELECT 
                    c.TABLE_SCHEMA,
                    c.TABLE_NAME,
                    c.COLUMN_NAME,
                    c.ORDINAL_POSITION,
                    c.COLUMN_DEFAULT,
                    c.IS_NULLABLE,
                    c.DATA_TYPE,
                    c.CHARACTER_MAXIMUM_LENGTH,
                    c.NUMERIC_PRECISION,
                    c.NUMERIC_SCALE,
                    c.DATETIME_PRECISION,
                    c.CHARACTER_SET_NAME,
                    c.COLLATION_NAME,
                    c.COLUMN_TYPE,
                    c.COLUMN_KEY,
                    c.EXTRA,
                    c.COLUMN_COMMENT
                FROM information_schema.COLUMNS c
                WHERE ({batch_where})
                ORDER BY c.TABLE_SCHEMA, c.TABLE_NAME, c.ORDINAL_POSITION
                """)
                
                try:
                    batch_num = i//batch_size + 1
                    total_batches = (len(table_list) + batch_size - 1)//batch_size
                    logger.debug(f"Discovering columns for batch {batch_num}/{total_batches} (SSH tunnel optimized)")
                    
                    # Execute with shorter timeout for SSH tunnels
                    column_results = await connection.execute_query(columns_query)
                    
                    # Process column results with success counter
                    columns_found = 0
                    for row in column_results:
                        schema_name = row[0]
                        table_name = row[1]
                        column_name = row[2]
                        table_key = f"{schema_name}.{table_name}"
                        
                        if table_key in tables:
                            tables[table_key]["columns"][column_name] = {
                                "ordinal_position": row[3],
                                "column_default": row[4],
                                "is_nullable": row[5] == "YES",
                                "data_type": row[6],
                                "character_maximum_length": row[7],
                                "numeric_precision": row[8],
                                "numeric_scale": row[9],
                                "datetime_precision": row[10],
                                "character_set": row[11],
                                "collation": row[12],
                                "column_type": row[13],
                                "column_key": row[14],
                                "extra": row[15],
                                "comment": row[16]
                            }
                            columns_found += 1
                    
                    logger.debug(f"Batch {batch_num}: discovered {columns_found} columns successfully")
                    
                except Exception as e:
                    logger.warning(f"Failed to discover columns for batch {i//batch_size + 1}: {e}")
                    # Mark tables in failed batch as incomplete but continue
                    for schema_name, table_name in batch:
                        table_key = f"{schema_name}.{table_name}"
                        if table_key in tables:
                            tables[table_key]["columns"] = {}
                            tables[table_key]["_discovery_error"] = str(e)
                    continue
            
            logger.debug(f"Discovery complete: {len(tables)} tables with columns")
            return tables
            
        except Exception as e:
            logger.error(f"Failed to discover objects in chunked mode: {e}")
            # Return partial results if any tables were discovered
            if tables:
                logger.warning(f"Returning partial discovery results: {len(tables)} tables with potential column discovery issues")
                return tables
            
            # Only fallback if no tables were discovered at all
            logger.info("No tables discovered, attempting fallback to original discovery method...")
            try:
                fallback_result = await self._discover_objects_fallback(connection)
                if not fallback_result:
                    # If fallback also fails and returns empty results, raise an exception
                    # to prevent false "target only" comparisons
                    error_msg = f"Failed to discover any table data from database. Original error: {e}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                return fallback_result
            except Exception as fallback_error:
                error_msg = f"Both chunked and fallback discovery failed. Database may be unreachable. Chunked error: {e}. Fallback error: {fallback_error}"
                logger.error(error_msg)
                raise Exception(error_msg)
    
    async def _discover_objects_fallback(self, connection: DatabaseConnection) -> Dict[str, Any]:
        """Fallback to original discovery method if chunking fails"""
        logger.warning("Using fallback discovery method due to chunking failure")
        
        query = text("""
        SELECT 
            t.TABLE_SCHEMA,
            t.TABLE_NAME,
            t.ENGINE,
            t.TABLE_COLLATION,
            t.TABLE_COMMENT,
            t.CREATE_OPTIONS,
            c.COLUMN_NAME,
            c.ORDINAL_POSITION,
            c.COLUMN_DEFAULT,
            c.IS_NULLABLE,
            c.DATA_TYPE,
            c.CHARACTER_MAXIMUM_LENGTH,
            c.NUMERIC_PRECISION,
            c.NUMERIC_SCALE,
            c.DATETIME_PRECISION,
            c.CHARACTER_SET_NAME,
            c.COLLATION_NAME,
            c.COLUMN_TYPE,
            c.COLUMN_KEY,
            c.EXTRA,
            c.COLUMN_COMMENT
        FROM information_schema.TABLES t
        JOIN information_schema.COLUMNS c 
            ON t.TABLE_SCHEMA = c.TABLE_SCHEMA 
            AND t.TABLE_NAME = c.TABLE_NAME
        WHERE t.TABLE_SCHEMA NOT IN :system_dbs
            AND t.TABLE_TYPE = 'BASE TABLE'
        ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME, c.ORDINAL_POSITION
        """)
        
        results = await connection.execute_query(
            query,
            {"system_dbs": tuple(settings.SYSTEM_DATABASES)}
        )
        
        tables = {}
        for row in results:
            schema_name = row[0]
            table_name = row[1]
            
            # Skip if filtered out
            if not self.should_compare_object(schema_name, table_name):
                continue
            
            table_key = f"{schema_name}.{table_name}"
            
            if table_key not in tables:
                tables[table_key] = {
                    "schema_name": schema_name,
                    "table_name": table_name,
                    "engine": row[2],
                    "collation": row[3],
                    "comment": row[4],
                    "create_options": row[5],
                    "columns": {}
                }
            
            # Add column information
            column_name = row[6]
            tables[table_key]["columns"][column_name] = {
                "ordinal_position": row[7],
                "column_default": row[8],
                "is_nullable": row[9] == "YES",
                "data_type": row[10],
                "character_maximum_length": row[11],
                "numeric_precision": row[12],
                "numeric_scale": row[13],
                "datetime_precision": row[14],
                "character_set": row[15],
                "collation": row[16],
                "column_type": row[17],
                "column_key": row[18],
                "extra": row[19],
                "comment": row[20]
            }
        
        return tables
    
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
        table_key: str,
        source_table: Dict[str, Any],
        target_table: Dict[str, Any]
    ) -> List[Difference]:
        """Compare a single table including its columns"""
        differences = []
        schema_name = source_table["schema_name"]
        table_name = source_table["table_name"]
        
        # Compare table-level properties
        if source_table["engine"] != target_table["engine"]:
            differences.append(Difference(
                diff_type=DiffType.TABLE_MISSING_TARGET,  # Using as table property changed
                severity=SeverityLevel.MEDIUM,
                object_type=ObjectType.TABLE,
                schema_name=schema_name,
                object_name=table_name,
                sub_object_name="engine",
                source_value=source_table["engine"],
                target_value=target_table["engine"],
                description=f"Table engine differs: {source_table['engine']} → {target_table['engine']}",
                can_auto_fix=True,
                fix_order=self.get_fix_order()
            ))
        
        # Compare table comment
        if not self.options.ignore_comments:
            if source_table.get("comment") != target_table.get("comment"):
                differences.append(Difference(
                    diff_type=DiffType.TABLE_MISSING_TARGET,  # Using as table property changed
                    severity=SeverityLevel.LOW,
                    object_type=ObjectType.TABLE,
                    schema_name=schema_name,
                    object_name=table_name,
                    sub_object_name="comment",
                    source_value=source_table.get("comment"),
                    target_value=target_table.get("comment"),
                    description=f"Table comment differs: {source_table.get('comment') or '(none)'} → {target_table.get('comment') or '(none)'}",
                    can_auto_fix=True,
                    fix_order=self.get_fix_order()
                ))
        
        # Compare table collation
        if not self.options.ignore_collation:
            if source_table.get("collation") != target_table.get("collation"):
                differences.append(Difference(
                    diff_type=DiffType.TABLE_MISSING_TARGET,  # Using as table property changed
                    severity=SeverityLevel.MEDIUM,
                    object_type=ObjectType.TABLE,
                    schema_name=schema_name,
                    object_name=table_name,
                    sub_object_name="collation",
                    source_value=source_table.get("collation"),
                    target_value=target_table.get("collation"),
                    description=f"Table collation differs: {source_table.get('collation')} → {target_table.get('collation')}",
                    can_auto_fix=True,
                    fix_order=self.get_fix_order()
                ))
        
        # Compare columns
        source_columns = source_table["columns"]
        target_columns = target_table["columns"]

        # Collect columns that exist only in source or only in target
        source_only_cols = {}  # Column name -> column info
        target_only_cols = {}  # Column name -> column info

        for col_name in source_columns:
            if col_name not in target_columns:
                source_only_cols[col_name] = source_columns[col_name]

        for col_name in target_columns:
            if col_name not in source_columns:
                target_only_cols[col_name] = target_columns[col_name]

        # Detect renames: match source-only columns with target-only columns
        # based on similar properties (type, nullable, default, extra)
        renamed_pairs = []  # List of (source_name, target_name, source_col, target_col)
        matched_source_cols = set()
        matched_target_cols = set()

        for source_name, source_col in source_only_cols.items():
            for target_name, target_col in target_only_cols.items():
                if target_name in matched_target_cols:
                    continue

                # Check if columns have matching properties (likely a rename)
                if self._columns_are_similar(source_col, target_col):
                    renamed_pairs.append((source_name, target_name, source_col, target_col))
                    matched_source_cols.add(source_name)
                    matched_target_cols.add(target_name)
                    break

        # Create COLUMN_RENAMED differences
        for source_name, target_name, source_col, target_col in renamed_pairs:
            differences.append(Difference(
                diff_type=DiffType.COLUMN_RENAMED,
                severity=SeverityLevel.MEDIUM,
                object_type=ObjectType.COLUMN,
                schema_name=schema_name,
                object_name=table_name,
                sub_object_name=source_name,  # Store source name as the primary
                source_value=source_col,  # Full source column info
                target_value=target_col,  # Full target column info (has the current name)
                source_display_value=source_name,  # Source column name (desired)
                target_display_value=target_name,  # Target column name (current)
                description=f"Column renamed: '{target_name}' → '{source_name}'",
                can_auto_fix=True,
                fix_order=self.get_fix_order() + 1
            ))

        # Create COLUMN_REMOVED for unmatched source-only columns
        for col_name in source_only_cols:
            if col_name not in matched_source_cols:
                differences.append(Difference(
                    diff_type=DiffType.COLUMN_REMOVED,
                    severity=SeverityLevel.CRITICAL,
                    object_type=ObjectType.COLUMN,
                    schema_name=schema_name,
                    object_name=table_name,
                    sub_object_name=col_name,
                    source_value=source_only_cols[col_name],
                    target_value=None,
                    description=f"Column '{col_name}' exists only in source",
                    can_auto_fix=True,
                    fix_order=self.get_fix_order() + 1,
                    warnings=["Potential data loss if column is dropped"]
                ))

        # Create COLUMN_ADDED for unmatched target-only columns
        for col_name in target_only_cols:
            if col_name not in matched_target_cols:
                differences.append(Difference(
                    diff_type=DiffType.COLUMN_ADDED,
                    severity=SeverityLevel.LOW,
                    object_type=ObjectType.COLUMN,
                    schema_name=schema_name,
                    object_name=table_name,
                    sub_object_name=col_name,
                    source_value=None,
                    target_value=target_only_cols[col_name],
                    description=f"Column '{col_name}' exists only in target",
                    can_auto_fix=True,
                    fix_order=self.get_fix_order() + 1
                ))

        # Columns that exist in both - compare properties
        common_columns = set(source_columns.keys()) & set(target_columns.keys())
        for column_name in common_columns:
            col_diffs = self._compare_column_properties(
                schema_name, table_name, column_name,
                source_columns[column_name], target_columns[column_name]
            )
            differences.extend(col_diffs)

        return differences
    
    def _compare_column_properties(
        self,
        schema_name: str,
        table_name: str,
        column_name: str,
        source_col: Dict[str, Any],
        target_col: Dict[str, Any]
    ) -> List[Difference]:
        """Compare column properties"""
        differences = []
        
        # Compare data type
        if source_col["column_type"] != target_col["column_type"]:
            differences.append(Difference(
                diff_type=DiffType.COLUMN_TYPE_CHANGED,
                severity=SeverityLevel.HIGH,
                object_type=ObjectType.COLUMN,
                schema_name=schema_name,
                object_name=table_name,
                sub_object_name=column_name,
                source_value=source_col,  # Pass full column info for proper MODIFY COLUMN
                target_value=target_col,  # Pass full column info for proper MODIFY COLUMN
                source_display_value=source_col["column_type"],
                target_display_value=target_col["column_type"],
                description=f"Column type changed: {source_col['column_type']} → {target_col['column_type']}",
                can_auto_fix=True,
                fix_order=self.get_fix_order() + 1,
                warnings=["Data conversion may be required", "Check for data compatibility"]
            ))
        
        # Compare nullable
        if source_col["is_nullable"] != target_col["is_nullable"]:
            differences.append(Difference(
                diff_type=DiffType.COLUMN_NULLABLE_CHANGED,
                severity=SeverityLevel.MEDIUM if target_col["is_nullable"] else SeverityLevel.HIGH,
                object_type=ObjectType.COLUMN,
                schema_name=schema_name,
                object_name=table_name,
                sub_object_name=column_name,
                source_value=source_col,  # Pass full column info
                target_value=target_col,  # Pass full column info
                source_display_value="YES" if source_col["is_nullable"] else "NO",
                target_display_value="YES" if target_col["is_nullable"] else "NO",
                description=f"Column nullable constraint changed",
                can_auto_fix=True,
                fix_order=self.get_fix_order() + 1,
                warnings=["Ensure no NULL values exist"] if not target_col["is_nullable"] else []
            ))
        
        # Compare default value
        if source_col["column_default"] != target_col["column_default"]:
            if not (self.options.ignore_auto_increment and "auto_increment" in str(source_col.get("extra", "")).lower()):
                differences.append(Difference(
                    diff_type=DiffType.COLUMN_DEFAULT_CHANGED,
                    severity=SeverityLevel.LOW,
                    object_type=ObjectType.COLUMN,
                    schema_name=schema_name,
                    object_name=table_name,
                    sub_object_name=column_name,
                    source_value=source_col,  # Pass full column info for proper MODIFY COLUMN
                    target_value=target_col,  # Pass full column info for proper MODIFY COLUMN
                    source_display_value=str(source_col["column_default"]) if source_col["column_default"] is not None else "NULL",
                    target_display_value=str(target_col["column_default"]) if target_col["column_default"] is not None else "NULL",
                    description=f"Column default value changed",
                    can_auto_fix=True,
                    fix_order=self.get_fix_order() + 1
                ))
        
        # Compare extra (auto_increment, etc.)
        if source_col["extra"] != target_col["extra"]:
            if not (self.options.ignore_auto_increment and "auto_increment" in source_col["extra"].lower()):
                differences.append(Difference(
                    diff_type=DiffType.COLUMN_EXTRA_CHANGED,
                    severity=SeverityLevel.MEDIUM,
                    object_type=ObjectType.COLUMN,
                    schema_name=schema_name,
                    object_name=table_name,
                    sub_object_name=column_name,
                    source_value=source_col,  # Pass full column info for proper MODIFY COLUMN
                    target_value=target_col,  # Pass full column info for proper MODIFY COLUMN
                    source_display_value=source_col["extra"] or "(none)",
                    target_display_value=target_col["extra"] or "(none)",
                    description=f"Column extra properties changed",
                    can_auto_fix=True,
                    fix_order=self.get_fix_order() + 1
                ))
        
        # Compare comment
        if not self.options.ignore_comments:
            if source_col["comment"] != target_col["comment"]:
                differences.append(Difference(
                    diff_type=DiffType.COLUMN_EXTRA_CHANGED,
                    severity=SeverityLevel.LOW,
                    object_type=ObjectType.COLUMN,
                    schema_name=schema_name,
                    object_name=table_name,
                    sub_object_name=column_name,
                    source_value=source_col,  # Pass full column info for proper MODIFY COLUMN
                    target_value=target_col,  # Pass full column info for proper MODIFY COLUMN
                    source_display_value=f"comment: {source_col['comment'] or '(none)'}",
                    target_display_value=f"comment: {target_col['comment'] or '(none)'}",
                    description=f"Column comment changed",
                    can_auto_fix=True,
                    fix_order=self.get_fix_order() + 1
                ))
        
        # Compare charset
        if not self.options.ignore_charset:
            if source_col.get("character_set") != target_col.get("character_set"):
                # Only compare charset for character-based columns
                if source_col.get("character_set") or target_col.get("character_set"):
                    differences.append(Difference(
                        diff_type=DiffType.COLUMN_EXTRA_CHANGED,
                        severity=SeverityLevel.MEDIUM,
                        object_type=ObjectType.COLUMN,
                        schema_name=schema_name,
                        object_name=table_name,
                        sub_object_name=column_name,
                        source_value=source_col,  # Pass full column info for proper MODIFY COLUMN
                        target_value=target_col,  # Pass full column info for proper MODIFY COLUMN
                        source_display_value=f"charset: {source_col.get('character_set') or '(none)'}",
                        target_display_value=f"charset: {target_col.get('character_set') or '(none)'}",
                        description=f"Column character set changed",
                        can_auto_fix=True,
                        fix_order=self.get_fix_order() + 1
                    ))
        
        # Compare collation
        if not self.options.ignore_collation:
            if source_col.get("collation") != target_col.get("collation"):
                # Only compare collation for character-based columns
                if source_col.get("collation") or target_col.get("collation"):
                    differences.append(Difference(
                        diff_type=DiffType.COLUMN_EXTRA_CHANGED,
                        severity=SeverityLevel.MEDIUM,
                        object_type=ObjectType.COLUMN,
                        schema_name=schema_name,
                        object_name=table_name,
                        sub_object_name=column_name,
                        source_value=source_col,  # Pass full column info for proper MODIFY COLUMN
                        target_value=target_col,  # Pass full column info for proper MODIFY COLUMN
                        source_display_value=f"collation: {source_col.get('collation') or '(none)'}",
                        target_display_value=f"collation: {target_col.get('collation') or '(none)'}",
                        description=f"Column collation changed",
                        can_auto_fix=True,
                        fix_order=self.get_fix_order() + 1
                    ))

        return differences

    def _columns_are_similar(
        self,
        source_col: Dict[str, Any],
        target_col: Dict[str, Any]
    ) -> bool:
        """Check if two columns are similar enough to be considered a rename.

        Columns are considered similar if they have matching:
        - column_type (data type with length/precision)
        - is_nullable
        - column_default (or both are None)
        - extra (auto_increment, etc.)

        We don't check ordinal_position because column order might change during rename.
        We don't check comment because that's often changed during rename.
        """
        # Column type must match exactly
        if source_col.get("column_type") != target_col.get("column_type"):
            return False

        # Nullable must match
        if source_col.get("is_nullable") != target_col.get("is_nullable"):
            return False

        # Default value must match (comparing as strings for consistency)
        source_default = source_col.get("column_default")
        target_default = target_col.get("column_default")
        if str(source_default) != str(target_default):
            return False

        # Extra (auto_increment, etc.) must match
        source_extra = (source_col.get("extra") or "").lower()
        target_extra = (target_col.get("extra") or "").lower()
        if source_extra != target_extra:
            return False

        return True
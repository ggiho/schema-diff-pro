from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
import re
import logging

from models.base import SyncScript, SyncDirection
from services.generators.sync_generator import SyncScriptGenerator
from core.database import DatabaseConnection
from .comparison import comparison_results, comparison_connections

logger = logging.getLogger(__name__)

router = APIRouter()


class SyncScriptRequest(BaseModel):
    """Request body for sync script generation"""
    direction: SyncDirection = SyncDirection.SOURCE_TO_TARGET


@router.post("/{comparison_id}/generate")
async def generate_sync_script(
    comparison_id: str,
    request: Optional[SyncScriptRequest] = None
) -> SyncScript:
    """
    Generate synchronization script from comparison results.
    
    Args:
        comparison_id: The comparison ID to generate script for
        request: Optional request body with sync direction
            - direction: 
                - "source_to_target": Make target DB match source (default)
                - "target_to_source": Make source DB match target
    
    Returns:
        SyncScript with forward and rollback SQL statements
    """
    if comparison_id not in comparison_results:
        raise HTTPException(status_code=404, detail="Comparison not found")
    
    result = comparison_results[comparison_id]
    
    if not result.differences:
        raise HTTPException(status_code=400, detail="No differences found to sync")
    
    # Use direction from request or default
    direction = request.direction if request else SyncDirection.SOURCE_TO_TARGET
    
    generator = SyncScriptGenerator(result.differences, comparison_id, direction)
    sync_script = generator.generate_sync_script()
    
    return sync_script


@router.get("/{comparison_id}/preview")
async def preview_sync_changes(comparison_id: str) -> Dict[str, Any]:
    """Preview what changes will be made by sync script"""
    if comparison_id not in comparison_results:
        raise HTTPException(status_code=404, detail="Comparison not found")
    
    result = comparison_results[comparison_id]
    
    # Group changes by type and severity
    preview = {
        "total_changes": len(result.differences),
        "by_severity": {},
        "by_operation": {
            "create": [],
            "modify": [],
            "drop": []
        },
        "warnings": [],
        "estimated_duration": 0
    }
    
    for diff in result.differences:
        # Count by severity
        severity = diff.severity.value
        preview["by_severity"][severity] = preview["by_severity"].get(severity, 0) + 1
        
        # Categorize by operation
        if "missing_target" in diff.diff_type.value:
            preview["by_operation"]["create"].append({
                "object": f"{diff.object_type.value} {diff.schema_name}.{diff.object_name}",
                "description": diff.description
            })
        elif "missing_source" in diff.diff_type.value:
            preview["by_operation"]["drop"].append({
                "object": f"{diff.object_type.value} {diff.schema_name}.{diff.object_name}",
                "description": diff.description,
                "warning": "Data loss risk!" if diff.object_type.value in ["table", "column"] else None
            })
        else:
            preview["by_operation"]["modify"].append({
                "object": f"{diff.object_type.value} {diff.schema_name}.{diff.object_name}",
                "description": diff.description
            })
        
        # Collect warnings
        preview["warnings"].extend(diff.warnings)
    
    # Estimate duration (rough)
    preview["estimated_duration"] = len(result.differences) * 5  # 5 seconds per change
    
    return preview


@router.post("/{comparison_id}/validate")
async def validate_sync_script(comparison_id: str) -> Dict[str, Any]:
    """Validate sync script before execution"""
    if comparison_id not in comparison_results:
        raise HTTPException(status_code=404, detail="Comparison not found")
    
    result = comparison_results[comparison_id]
    
    validation = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "pre_checks": []
    }
    
    # Check for critical operations
    for diff in result.differences:
        if diff.severity.value == "critical":
            validation["warnings"].append(f"Critical change: {diff.description}")
        
        # Check for data loss risks
        if any("data loss" in w.lower() for w in diff.warnings):
            validation["warnings"].append(f"Data loss risk in {diff.object_name}: {diff.description}")
            validation["pre_checks"].append(f"Backup {diff.schema_name}.{diff.object_name}")
    
    # Add general pre-checks
    validation["pre_checks"].extend([
        "Ensure full database backup exists",
        "Verify no active transactions on affected tables",
        "Check available disk space for operations",
        "Confirm maintenance window if downtime required"
    ])
    
    return validation


class ExecuteScriptRequest(BaseModel):
    """Request body for script execution"""
    script: str
    target_database: str  # 'source' or 'target'


class ExecuteScriptResponse(BaseModel):
    """Response for script execution"""
    success: bool
    executed_statements: int
    failed_statements: int
    results: List[Dict[str, Any]]
    warnings: List[str]
    errors: List[str]


def analyze_script_risks(script: str) -> Dict[str, Any]:
    """Analyze script for dangerous operations"""
    risks = {
        "has_drop_table": False,
        "has_drop_column": False,
        "has_drop_index": False,
        "has_drop_constraint": False,
        "has_truncate": False,
        "has_delete": False,
        "drop_tables": [],
        "drop_columns": [],
        "risk_level": "low",  # low, medium, high
        "warnings": []
    }
    
    script_upper = script.upper()
    
    # Check for DROP TABLE
    drop_table_pattern = re.compile(r'DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?[`"\']?(\w+)[`"\']?\s*\.\s*[`"\']?(\w+)[`"\']?', re.IGNORECASE)
    drop_tables = drop_table_pattern.findall(script)
    if drop_tables:
        risks["has_drop_table"] = True
        risks["drop_tables"] = [f"{schema}.{table}" for schema, table in drop_tables]
        risks["risk_level"] = "high"
        risks["warnings"].append(f"Script contains DROP TABLE statements: {', '.join(risks['drop_tables'])}")
    
    # Check for DROP COLUMN
    drop_column_pattern = re.compile(r'DROP\s+COLUMN\s+[`"\']?(\w+)[`"\']?', re.IGNORECASE)
    drop_columns = drop_column_pattern.findall(script)
    if drop_columns:
        risks["has_drop_column"] = True
        risks["drop_columns"] = drop_columns
        risks["risk_level"] = "high" if risks["risk_level"] != "high" else "high"
        risks["warnings"].append(f"Script contains DROP COLUMN statements: {', '.join(drop_columns)}")
    
    # Check for DROP INDEX
    if re.search(r'DROP\s+INDEX', script_upper):
        risks["has_drop_index"] = True
        if risks["risk_level"] == "low":
            risks["risk_level"] = "medium"
        risks["warnings"].append("Script contains DROP INDEX statements")
    
    # Check for DROP CONSTRAINT
    if re.search(r'DROP\s+CONSTRAINT', script_upper) or re.search(r'DROP\s+FOREIGN\s+KEY', script_upper):
        risks["has_drop_constraint"] = True
        if risks["risk_level"] == "low":
            risks["risk_level"] = "medium"
        risks["warnings"].append("Script contains DROP CONSTRAINT statements")
    
    # Check for TRUNCATE
    if 'TRUNCATE' in script_upper:
        risks["has_truncate"] = True
        risks["risk_level"] = "high"
        risks["warnings"].append("Script contains TRUNCATE statements - all data will be deleted!")
    
    # Check for DELETE
    if re.search(r'\bDELETE\s+FROM\b', script_upper):
        risks["has_delete"] = True
        risks["risk_level"] = "high"
        risks["warnings"].append("Script contains DELETE statements")
    
    return risks


@router.post("/{comparison_id}/analyze")
async def analyze_script(
    comparison_id: str,
    request: ExecuteScriptRequest
) -> Dict[str, Any]:
    """Analyze script for risks before execution"""
    if comparison_id not in comparison_results:
        raise HTTPException(status_code=404, detail="Comparison not found")
    
    risks = analyze_script_risks(request.script)
    
    return {
        "comparison_id": comparison_id,
        "target_database": request.target_database,
        "risks": risks,
        "requires_confirmation": risks["risk_level"] in ["medium", "high"]
    }


@router.post("/{comparison_id}/execute")
async def execute_sync_script(
    comparison_id: str,
    request: ExecuteScriptRequest
) -> ExecuteScriptResponse:
    """
    Execute sync script on the specified database.
    
    WARNING: This will modify the database schema!
    """
    if comparison_id not in comparison_results:
        raise HTTPException(status_code=404, detail="Comparison not found")
    
    if comparison_id not in comparison_connections:
        raise HTTPException(
            status_code=400, 
            detail="Connection information not available. Please run comparison again."
        )
    
    if request.target_database not in ['source', 'target']:
        raise HTTPException(
            status_code=400,
            detail="target_database must be 'source' or 'target'"
        )
    
    # Get connection config
    connections = comparison_connections[comparison_id]
    config = connections[request.target_database]
    
    # Analyze risks
    risks = analyze_script_risks(request.script)
    
    # Parse script into statements
    statements = parse_sql_statements(request.script)
    
    if not statements:
        raise HTTPException(status_code=400, detail="No valid SQL statements found in script")
    
    logger.info(f"Executing {len(statements)} statements on {request.target_database} database")
    logger.info(f"Risk level: {risks['risk_level']}")
    if risks['warnings']:
        for warning in risks['warnings']:
            logger.warning(warning)
    
    # Execute statements
    results = []
    executed = 0
    failed = 0
    errors = []
    
    connection = None
    try:
        # Build connection URL from config
        connection_url = config.get_connection_url()
        connection = DatabaseConnection(connection_url, database=config.database)
        
        # Test connection
        await connection.execute_query("SELECT 1")
        logger.info(f"Connected to {request.target_database} database successfully")
        
        for i, stmt in enumerate(statements):
            stmt_result = {
                "index": i,
                "statement": stmt[:100] + "..." if len(stmt) > 100 else stmt,
                "full_statement": stmt,  # Keep full statement for debugging
                "success": False,
                "error": None,
                "rows_affected": 0
            }
            
            try:
                # Execute DDL statement (doesn't return rows)
                await connection.execute_ddl(stmt)
                stmt_result["success"] = True
                stmt_result["rows_affected"] = 0
                executed += 1
                logger.info(f"Statement {i+1}/{len(statements)} executed successfully")
                
            except Exception as e:
                stmt_result["error"] = str(e)
                failed += 1
                errors.append(f"Statement {i+1}: {str(e)}")
                logger.error(f"Statement {i+1} failed: {e}")
                # Continue with next statement
            
            results.append(stmt_result)
    
    except Exception as e:
        logger.error(f"Connection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to connect to database: {str(e)}")
    
    finally:
        if connection:
            await connection.close()
    
    return ExecuteScriptResponse(
        success=failed == 0,
        executed_statements=executed,
        failed_statements=failed,
        results=results,
        warnings=risks["warnings"],
        errors=errors
    )


def parse_sql_statements(script: str) -> List[str]:
    """Parse SQL script into individual statements.

    Properly handles:
    - Semicolons inside string literals: 'test; value'
    - Comment markers inside strings: 'test--value'
    - Escaped quotes: 'it''s working'
    - Multi-line statements
    """
    statements = []
    current_stmt = []
    in_string = False
    string_char = None
    i = 0

    while i < len(script):
        char = script[i]

        # Handle string literals
        if char in ("'", '"') and not in_string:
            in_string = True
            string_char = char
            current_stmt.append(char)
            i += 1
            continue

        if in_string:
            current_stmt.append(char)
            # Check for escaped quote ('' or "")
            if char == string_char:
                # Look ahead for escaped quote
                if i + 1 < len(script) and script[i + 1] == string_char:
                    current_stmt.append(script[i + 1])
                    i += 2
                    continue
                else:
                    # End of string
                    in_string = False
                    string_char = None
            i += 1
            continue

        # Outside string - handle comments and semicolons

        # Check for line comment (--)
        if char == '-' and i + 1 < len(script) and script[i + 1] == '-':
            # Skip until end of line
            while i < len(script) and script[i] != '\n':
                i += 1
            continue

        # Check for hash comment (#)
        if char == '#':
            # Skip until end of line
            while i < len(script) and script[i] != '\n':
                i += 1
            continue

        # Check for block comment (/* */)
        if char == '/' and i + 1 < len(script) and script[i + 1] == '*':
            i += 2
            while i + 1 < len(script):
                if script[i] == '*' and script[i + 1] == '/':
                    i += 2
                    break
                i += 1
            continue

        # Statement terminator
        if char == ';':
            stmt = ''.join(current_stmt).strip()
            if stmt:
                # Only include DDL statements
                stmt_upper = stmt.upper()
                if not stmt_upper.startswith(('SET ', 'USE ')):
                    if any(keyword in stmt_upper for keyword in [
                        'CREATE', 'ALTER', 'DROP', 'ADD', 'MODIFY', 'CHANGE', 'RENAME'
                    ]):
                        statements.append(stmt)
                        logger.info(f"Parsed statement: {stmt[:80]}...")
                    else:
                        logger.warning(f"Skipped statement (no DDL keyword): {stmt[:80]}...")
            current_stmt = []
            i += 1
            continue

        current_stmt.append(char)
        i += 1

    # Handle last statement without semicolon
    stmt = ''.join(current_stmt).strip()
    if stmt:
        stmt_upper = stmt.upper()
        if not stmt_upper.startswith(('SET ', 'USE ')):
            if any(keyword in stmt_upper for keyword in [
                'CREATE', 'ALTER', 'DROP', 'ADD', 'MODIFY', 'CHANGE', 'RENAME'
            ]):
                statements.append(stmt)
                logger.info(f"Parsed statement: {stmt[:80]}...")

    logger.info(f"Total parsed statements: {len(statements)}")
    return statements
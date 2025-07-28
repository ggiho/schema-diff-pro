from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from models.base import SyncScript
from services.generators.sync_generator import SyncScriptGenerator
from .comparison import comparison_results

router = APIRouter()


@router.post("/{comparison_id}/generate")
async def generate_sync_script(comparison_id: str) -> SyncScript:
    """Generate synchronization script from comparison results"""
    if comparison_id not in comparison_results:
        raise HTTPException(status_code=404, detail="Comparison not found")
    
    result = comparison_results[comparison_id]
    
    if not result.differences:
        raise HTTPException(status_code=400, detail="No differences found to sync")
    
    generator = SyncScriptGenerator(result.differences, comparison_id)
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
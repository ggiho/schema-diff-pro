"""
Unit tests for SyncScriptGenerator
Tests the new SyncDirection feature
"""

import pytest
from typing import List

from services.generators.sync_generator import SyncScriptGenerator
from models.base import (
    Difference, DiffType, SeverityLevel, ObjectType, SyncDirection
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_differences() -> List[Difference]:
    """Create sample differences for testing"""
    return [
        Difference(
            diff_type=DiffType.TABLE_MISSING_TARGET,
            severity=SeverityLevel.HIGH,
            object_type=ObjectType.TABLE,
            schema_name="test_db",
            object_name="users",
            source_value={"table_name": "users", "engine": "InnoDB"},
            target_value=None,
            description="Table 'users' exists only in source",
            can_auto_fix=True,
            fix_order=2,
        ),
        Difference(
            diff_type=DiffType.COLUMN_REMOVED,
            severity=SeverityLevel.CRITICAL,
            object_type=ObjectType.COLUMN,
            schema_name="test_db",
            object_name="orders",
            sub_object_name="discount",
            source_value={"column_type": "decimal(10,2)", "is_nullable": True},
            target_value=None,
            description="Column 'discount' exists only in source",
            can_auto_fix=True,
            fix_order=3,
            warnings=["Potential data loss if column is dropped"],
        ),
        Difference(
            diff_type=DiffType.INDEX_MISSING_SOURCE,
            severity=SeverityLevel.MEDIUM,
            object_type=ObjectType.INDEX,
            schema_name="test_db",
            object_name="products",
            sub_object_name="idx_price",
            source_value=None,
            target_value={"columns": "price", "is_unique": False, "index_type": "BTREE"},
            description="Index 'idx_price' exists only in target",
            can_auto_fix=True,
            fix_order=5,
        ),
    ]


# ============================================================================
# SyncDirection Tests
# ============================================================================

class TestSyncDirection:
    """Tests for SyncDirection feature"""

    def test_source_to_target_direction_default(self, sample_differences: List[Difference]):
        """Default direction should be SOURCE_TO_TARGET"""
        generator = SyncScriptGenerator(sample_differences, "test-id")
        
        assert generator.direction == SyncDirection.SOURCE_TO_TARGET
    
    def test_source_to_target_keeps_differences_unchanged(self, sample_differences: List[Difference]):
        """SOURCE_TO_TARGET should not transform differences"""
        generator = SyncScriptGenerator(
            sample_differences, 
            "test-id", 
            SyncDirection.SOURCE_TO_TARGET
        )
        
        # Differences should be unchanged
        assert len(generator.differences) == len(sample_differences)
        assert generator.differences[0].diff_type == DiffType.TABLE_MISSING_TARGET
        assert generator.differences[1].diff_type == DiffType.COLUMN_REMOVED
        assert generator.differences[2].diff_type == DiffType.INDEX_MISSING_SOURCE
    
    def test_target_to_source_reverses_diff_types(self, sample_differences: List[Difference]):
        """TARGET_TO_SOURCE should reverse diff types"""
        generator = SyncScriptGenerator(
            sample_differences, 
            "test-id", 
            SyncDirection.TARGET_TO_SOURCE
        )
        
        # Diff types should be reversed
        assert generator.differences[0].diff_type == DiffType.TABLE_MISSING_SOURCE
        assert generator.differences[1].diff_type == DiffType.COLUMN_ADDED
        assert generator.differences[2].diff_type == DiffType.INDEX_MISSING_TARGET
    
    def test_target_to_source_swaps_values(self, sample_differences: List[Difference]):
        """TARGET_TO_SOURCE should swap source and target values"""
        generator = SyncScriptGenerator(
            sample_differences, 
            "test-id", 
            SyncDirection.TARGET_TO_SOURCE
        )
        
        # First difference: TABLE_MISSING_TARGET -> TABLE_MISSING_SOURCE
        # source_value and target_value should be swapped
        assert generator.differences[0].source_value is None
        assert generator.differences[0].target_value == {"table_name": "users", "engine": "InnoDB"}
        
        # Second difference: COLUMN_REMOVED -> COLUMN_ADDED
        assert generator.differences[1].source_value is None
        assert generator.differences[1].target_value == {"column_type": "decimal(10,2)", "is_nullable": True}
    
    def test_script_header_includes_direction_source_to_target(self, sample_differences: List[Difference]):
        """Script header should indicate SOURCE_TO_TARGET direction"""
        generator = SyncScriptGenerator(
            sample_differences, 
            "test-id", 
            SyncDirection.SOURCE_TO_TARGET
        )
        
        script = generator.generate_sync_script()
        
        assert "source_to_target" in script.forward_script
        assert "Making TARGET database match SOURCE" in script.forward_script
        assert "Source → Target" in script.forward_script
    
    def test_script_header_includes_direction_target_to_source(self, sample_differences: List[Difference]):
        """Script header should indicate TARGET_TO_SOURCE direction"""
        generator = SyncScriptGenerator(
            sample_differences, 
            "test-id", 
            SyncDirection.TARGET_TO_SOURCE
        )
        
        script = generator.generate_sync_script()
        
        assert "target_to_source" in script.forward_script
        assert "Making SOURCE database match TARGET" in script.forward_script
        assert "Target → Source" in script.forward_script


class TestSyncScriptGeneration:
    """Tests for sync script SQL generation"""
    
    def test_generates_forward_and_rollback_scripts(self, sample_differences: List[Difference]):
        """Should generate both forward and rollback scripts"""
        generator = SyncScriptGenerator(sample_differences, "test-id")
        script = generator.generate_sync_script()
        
        assert script.forward_script is not None
        assert script.rollback_script is not None
        assert len(script.forward_script) > 0
        assert len(script.rollback_script) > 0
    
    def test_script_includes_foreign_key_checks(self, sample_differences: List[Difference]):
        """Scripts should disable/enable foreign key checks"""
        generator = SyncScriptGenerator(sample_differences, "test-id")
        script = generator.generate_sync_script()
        
        assert "SET FOREIGN_KEY_CHECKS = 0" in script.forward_script
        assert "SET FOREIGN_KEY_CHECKS = 1" in script.forward_script
    
    def test_data_loss_risk_detection(self, sample_differences: List[Difference]):
        """Should detect data loss risk from COLUMN_REMOVED"""
        generator = SyncScriptGenerator(sample_differences, "test-id")
        script = generator.generate_sync_script()
        
        # COLUMN_REMOVED should trigger data loss risk
        assert script.data_loss_risk is True
    
    def test_empty_differences_raises_or_handles(self):
        """Should handle empty differences list"""
        generator = SyncScriptGenerator([], "test-id")
        script = generator.generate_sync_script()
        
        # Should generate scripts even with no differences
        assert script is not None
        assert "Total statements: 0" in script.forward_script
    
    def test_impact_analysis_includes_affected_tables(self, sample_differences: List[Difference]):
        """Impact analysis should list affected tables"""
        generator = SyncScriptGenerator(sample_differences, "test-id")
        script = generator.generate_sync_script()
        
        assert "tables_affected" in script.estimated_impact
        affected = script.estimated_impact["tables_affected"]
        assert "test_db.users" in affected or "test_db.orders" in affected


class TestDescriptionReversal:
    """Tests for description text reversal"""
    
    def test_reverses_source_only_description(self):
        """Should reverse 'exists only in source' descriptions"""
        diff = Difference(
            diff_type=DiffType.TABLE_MISSING_TARGET,
            severity=SeverityLevel.HIGH,
            object_type=ObjectType.TABLE,
            schema_name="db",
            object_name="test",
            description="Table 'test' exists only in source",
            can_auto_fix=True,
            fix_order=1,
        )
        
        generator = SyncScriptGenerator([diff], "test-id", SyncDirection.TARGET_TO_SOURCE)
        
        # Description should be reversed
        assert "target" in generator.differences[0].description.lower()
    
    def test_reverses_target_only_description(self):
        """Should reverse 'exists only in target' descriptions"""
        diff = Difference(
            diff_type=DiffType.TABLE_MISSING_SOURCE,
            severity=SeverityLevel.HIGH,
            object_type=ObjectType.TABLE,
            schema_name="db",
            object_name="test",
            description="Table 'test' exists only in target",
            can_auto_fix=True,
            fix_order=1,
        )
        
        generator = SyncScriptGenerator([diff], "test-id", SyncDirection.TARGET_TO_SOURCE)
        
        # Description should be reversed
        assert "source" in generator.differences[0].description.lower()

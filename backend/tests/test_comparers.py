"""
Unit tests for Comparer classes
Kent Beck approves: "Test-Driven Development is a design technique, not a testing technique."
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from services.comparers.base_comparer import BaseComparer
from services.comparers.table_comparer import TableComparer
from services.comparers.index_comparer import IndexComparer
from services.comparers.constraint_comparer import ConstraintComparer
from models.base import (
    ComparisonOptions, Difference, DiffType, SeverityLevel, ObjectType
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def default_options() -> ComparisonOptions:
    """Default comparison options for tests"""
    return ComparisonOptions(
        compare_tables=True,
        compare_columns=True,
        compare_indexes=True,
        compare_constraints=True,
        ignore_auto_increment=True,
        ignore_comments=False,
        ignore_charset=False,
        ignore_collation=False,
        case_sensitive=True,
    )


@pytest.fixture
def mock_source_connection():
    """Mock source database connection"""
    conn = AsyncMock()
    conn.connection_url = "mysql://test@localhost:3306/testdb"
    return conn


@pytest.fixture
def mock_target_connection():
    """Mock target database connection"""
    conn = AsyncMock()
    conn.connection_url = "mysql://test@localhost:3306/testdb"
    return conn


# ============================================================================
# TableComparer Tests
# ============================================================================

class TestTableComparer:
    """Tests for TableComparer"""

    @pytest.fixture
    def table_comparer(
        self, mock_source_connection, mock_target_connection, default_options
    ) -> TableComparer:
        return TableComparer(
            mock_source_connection,
            mock_target_connection,
            default_options,
            "test-comparison-id"
        )

    def test_object_type_is_table(self, table_comparer: TableComparer):
        """TableComparer should have TABLE object type"""
        assert table_comparer.object_type == ObjectType.TABLE

    @pytest.mark.asyncio
    async def test_compare_identical_tables_returns_no_differences(
        self, table_comparer: TableComparer
    ):
        """Comparing identical tables should return no differences"""
        source_table = self._create_table_data("test_schema", "users", {
            "id": self._create_column("id", "int", False),
            "name": self._create_column("name", "varchar(255)", True),
        })
        target_table = self._create_table_data("test_schema", "users", {
            "id": self._create_column("id", "int", False),
            "name": self._create_column("name", "varchar(255)", True),
        })

        differences = await table_comparer.compare_single_object(
            "test_schema.users", source_table, target_table
        )

        assert len(differences) == 0

    @pytest.mark.asyncio
    async def test_detect_column_type_change(self, table_comparer: TableComparer):
        """Should detect when column type changes"""
        source_table = self._create_table_data("test_schema", "users", {
            "name": self._create_column("name", "varchar(100)", True),
        })
        target_table = self._create_table_data("test_schema", "users", {
            "name": self._create_column("name", "varchar(255)", True),
        })

        differences = await table_comparer.compare_single_object(
            "test_schema.users", source_table, target_table
        )

        assert len(differences) == 1
        assert differences[0].diff_type == DiffType.COLUMN_TYPE_CHANGED
        assert differences[0].severity == SeverityLevel.HIGH
        assert differences[0].sub_object_name == "name"

    @pytest.mark.asyncio
    async def test_detect_missing_column_in_target(self, table_comparer: TableComparer):
        """Should detect column that exists only in source (removed from target)"""
        source_table = self._create_table_data("test_schema", "users", {
            "id": self._create_column("id", "int", False),
            "email": self._create_column("email", "varchar(255)", True),
        })
        target_table = self._create_table_data("test_schema", "users", {
            "id": self._create_column("id", "int", False),
        })

        differences = await table_comparer.compare_single_object(
            "test_schema.users", source_table, target_table
        )

        assert len(differences) == 1
        assert differences[0].diff_type == DiffType.COLUMN_REMOVED
        assert differences[0].severity == SeverityLevel.CRITICAL
        assert "data loss" in differences[0].warnings[0].lower()

    @pytest.mark.asyncio
    async def test_detect_new_column_in_target(self, table_comparer: TableComparer):
        """Should detect column that exists only in target (added)"""
        source_table = self._create_table_data("test_schema", "users", {
            "id": self._create_column("id", "int", False),
        })
        target_table = self._create_table_data("test_schema", "users", {
            "id": self._create_column("id", "int", False),
            "created_at": self._create_column("created_at", "timestamp", True),
        })

        differences = await table_comparer.compare_single_object(
            "test_schema.users", source_table, target_table
        )

        assert len(differences) == 1
        assert differences[0].diff_type == DiffType.COLUMN_ADDED
        assert differences[0].severity == SeverityLevel.LOW

    @pytest.mark.asyncio
    async def test_detect_nullable_change(self, table_comparer: TableComparer):
        """Should detect when nullable constraint changes"""
        source_table = self._create_table_data("test_schema", "users", {
            "name": self._create_column("name", "varchar(255)", True),
        })
        target_table = self._create_table_data("test_schema", "users", {
            "name": self._create_column("name", "varchar(255)", False),
        })

        differences = await table_comparer.compare_single_object(
            "test_schema.users", source_table, target_table
        )

        assert len(differences) == 1
        assert differences[0].diff_type == DiffType.COLUMN_NULLABLE_CHANGED

    @pytest.mark.asyncio
    async def test_detect_engine_change(self, table_comparer: TableComparer):
        """Should detect when table engine changes"""
        source_table = self._create_table_data(
            "test_schema", "users", {}, engine="InnoDB"
        )
        target_table = self._create_table_data(
            "test_schema", "users", {}, engine="MyISAM"
        )

        differences = await table_comparer.compare_single_object(
            "test_schema.users", source_table, target_table
        )

        assert len(differences) == 1
        assert differences[0].sub_object_name == "engine"
        assert "InnoDB" in differences[0].description
        assert "MyISAM" in differences[0].description

    @pytest.mark.asyncio
    async def test_ignore_auto_increment_when_option_set(
        self, mock_source_connection, mock_target_connection
    ):
        """Should ignore auto_increment differences when option is set"""
        options = ComparisonOptions(ignore_auto_increment=True)
        comparer = TableComparer(
            mock_source_connection,
            mock_target_connection,
            options,
            "test-id"
        )

        source_table = self._create_table_data("test_schema", "users", {
            "id": self._create_column("id", "int", False, extra="auto_increment"),
        })
        target_table = self._create_table_data("test_schema", "users", {
            "id": self._create_column("id", "int", False, extra=""),
        })

        differences = await comparer.compare_single_object(
            "test_schema.users", source_table, target_table
        )

        # auto_increment extra change should be ignored
        assert not any(d.diff_type == DiffType.COLUMN_EXTRA_CHANGED for d in differences)

    # Helper methods
    def _create_table_data(
        self,
        schema_name: str,
        table_name: str,
        columns: Dict[str, Dict],
        engine: str = "InnoDB"
    ) -> Dict[str, Any]:
        return {
            "schema_name": schema_name,
            "table_name": table_name,
            "engine": engine,
            "collation": "utf8mb4_general_ci",
            "comment": "",
            "create_options": "",
            "columns": columns,
        }

    def _create_column(
        self,
        name: str,
        column_type: str,
        is_nullable: bool,
        column_default: str = None,
        extra: str = ""
    ) -> Dict[str, Any]:
        return {
            "ordinal_position": 1,
            "column_default": column_default,
            "is_nullable": is_nullable,
            "data_type": column_type.split("(")[0],
            "character_maximum_length": None,
            "numeric_precision": None,
            "numeric_scale": None,
            "datetime_precision": None,
            "character_set": "utf8mb4",
            "collation": "utf8mb4_general_ci",
            "column_type": column_type,
            "column_key": "",
            "extra": extra,
            "comment": "",
        }


# ============================================================================
# IndexComparer Tests
# ============================================================================

class TestIndexComparer:
    """Tests for IndexComparer"""

    @pytest.fixture
    def index_comparer(
        self, mock_source_connection, mock_target_connection, default_options
    ) -> IndexComparer:
        return IndexComparer(
            mock_source_connection,
            mock_target_connection,
            default_options,
            "test-comparison-id"
        )

    def test_object_type_is_index(self, index_comparer: IndexComparer):
        """IndexComparer should have INDEX object type"""
        assert index_comparer.object_type == ObjectType.INDEX

    @pytest.mark.asyncio
    async def test_compare_identical_indexes_returns_no_differences(
        self, index_comparer: IndexComparer
    ):
        """Comparing identical indexes should return no differences"""
        source_index = self._create_index_data(
            "test_schema", "users", "idx_email", "email", is_unique=True
        )
        target_index = self._create_index_data(
            "test_schema", "users", "idx_email", "email", is_unique=True
        )

        differences = await index_comparer.compare_single_object(
            "test_schema.users.idx_email", source_index, target_index
        )

        assert len(differences) == 0

    @pytest.mark.asyncio
    async def test_detect_index_columns_change(self, index_comparer: IndexComparer):
        """Should detect when index columns change"""
        source_index = self._create_index_data(
            "test_schema", "users", "idx_name", "first_name"
        )
        target_index = self._create_index_data(
            "test_schema", "users", "idx_name", "first_name,last_name"
        )

        differences = await index_comparer.compare_single_object(
            "test_schema.users.idx_name", source_index, target_index
        )

        assert len(differences) == 1
        assert differences[0].diff_type == DiffType.INDEX_COLUMNS_CHANGED
        assert differences[0].severity == SeverityLevel.HIGH

    @pytest.mark.asyncio
    async def test_detect_uniqueness_change(self, index_comparer: IndexComparer):
        """Should detect when index uniqueness changes"""
        source_index = self._create_index_data(
            "test_schema", "users", "idx_email", "email", is_unique=False
        )
        target_index = self._create_index_data(
            "test_schema", "users", "idx_email", "email", is_unique=True
        )

        differences = await index_comparer.compare_single_object(
            "test_schema.users.idx_email", source_index, target_index
        )

        assert len(differences) == 1
        assert differences[0].diff_type == DiffType.INDEX_UNIQUE_CHANGED

    @pytest.mark.asyncio
    async def test_detect_index_type_change(self, index_comparer: IndexComparer):
        """Should detect when index type changes"""
        source_index = self._create_index_data(
            "test_schema", "users", "idx_text", "description", index_type="BTREE"
        )
        target_index = self._create_index_data(
            "test_schema", "users", "idx_text", "description", index_type="FULLTEXT"
        )

        differences = await index_comparer.compare_single_object(
            "test_schema.users.idx_text", source_index, target_index
        )

        assert len(differences) == 1
        assert differences[0].diff_type == DiffType.INDEX_TYPE_CHANGED
        assert differences[0].severity == SeverityLevel.MEDIUM

    # Helper methods
    def _create_index_data(
        self,
        schema_name: str,
        table_name: str,
        index_name: str,
        columns: str,
        is_unique: bool = False,
        index_type: str = "BTREE"
    ) -> Dict[str, Any]:
        return {
            "schema_name": schema_name,
            "table_name": table_name,
            "index_name": index_name,
            "is_unique": is_unique,
            "index_type": index_type,
            "columns": columns,
            "column_details": columns,
            "has_nullable": False,
            "comment": "",
        }


# ============================================================================
# ConstraintComparer Tests
# ============================================================================

class TestConstraintComparer:
    """Tests for ConstraintComparer"""

    @pytest.fixture
    def constraint_comparer(
        self, mock_source_connection, mock_target_connection, default_options
    ) -> ConstraintComparer:
        return ConstraintComparer(
            mock_source_connection,
            mock_target_connection,
            default_options,
            "test-comparison-id"
        )

    def test_object_type_is_constraint(self, constraint_comparer: ConstraintComparer):
        """ConstraintComparer should have CONSTRAINT object type"""
        assert constraint_comparer.object_type == ObjectType.CONSTRAINT

    @pytest.mark.asyncio
    async def test_compare_identical_pk_returns_no_differences(
        self, constraint_comparer: ConstraintComparer
    ):
        """Comparing identical primary keys should return no differences"""
        source_pk = self._create_pk_constraint("test_schema", "users", "id")
        target_pk = self._create_pk_constraint("test_schema", "users", "id")

        differences = await constraint_comparer.compare_single_object(
            "test_schema.users.PRIMARY", source_pk, target_pk
        )

        assert len(differences) == 0

    @pytest.mark.asyncio
    async def test_detect_pk_columns_change(
        self, constraint_comparer: ConstraintComparer
    ):
        """Should detect when primary key columns change"""
        source_pk = self._create_pk_constraint("test_schema", "users", "id")
        target_pk = self._create_pk_constraint("test_schema", "users", "id,tenant_id")

        differences = await constraint_comparer.compare_single_object(
            "test_schema.users.PRIMARY", source_pk, target_pk
        )

        assert len(differences) == 1
        assert differences[0].diff_type == DiffType.CONSTRAINT_DEFINITION_CHANGED
        assert differences[0].severity == SeverityLevel.HIGH

    @pytest.mark.asyncio
    async def test_detect_fk_reference_change(
        self, constraint_comparer: ConstraintComparer
    ):
        """Should detect when foreign key references different table"""
        source_fk = self._create_fk_constraint(
            "test_schema", "orders", "fk_user",
            "user_id", "users", "id"
        )
        target_fk = self._create_fk_constraint(
            "test_schema", "orders", "fk_user",
            "user_id", "customers", "id"
        )

        differences = await constraint_comparer.compare_single_object(
            "test_schema.orders.fk_user", source_fk, target_fk
        )

        assert len(differences) >= 1
        assert any(
            d.diff_type == DiffType.CONSTRAINT_DEFINITION_CHANGED
            for d in differences
        )

    @pytest.mark.asyncio
    async def test_detect_fk_rule_change(
        self, constraint_comparer: ConstraintComparer
    ):
        """Should detect when foreign key rules change"""
        source_fk = self._create_fk_constraint(
            "test_schema", "orders", "fk_user",
            "user_id", "users", "id",
            update_rule="CASCADE", delete_rule="CASCADE"
        )
        target_fk = self._create_fk_constraint(
            "test_schema", "orders", "fk_user",
            "user_id", "users", "id",
            update_rule="NO ACTION", delete_rule="SET NULL"
        )

        differences = await constraint_comparer.compare_single_object(
            "test_schema.orders.fk_user", source_fk, target_fk
        )

        assert len(differences) == 1
        assert differences[0].severity == SeverityLevel.MEDIUM

    # Helper methods
    def _create_pk_constraint(
        self, schema_name: str, table_name: str, columns: str
    ) -> Dict[str, Any]:
        return {
            "schema_name": schema_name,
            "table_name": table_name,
            "constraint_name": "PRIMARY",
            "constraint_type": "PRIMARY KEY",
            "columns": columns,
            "referenced_table_schema": None,
            "referenced_table_name": None,
            "referenced_columns": None,
            "update_rule": None,
            "delete_rule": None,
        }

    def _create_fk_constraint(
        self,
        schema_name: str,
        table_name: str,
        constraint_name: str,
        columns: str,
        ref_table: str,
        ref_columns: str,
        update_rule: str = "NO ACTION",
        delete_rule: str = "NO ACTION"
    ) -> Dict[str, Any]:
        return {
            "schema_name": schema_name,
            "table_name": table_name,
            "constraint_name": constraint_name,
            "constraint_type": "FOREIGN KEY",
            "columns": columns,
            "referenced_table_schema": schema_name,
            "referenced_table_name": ref_table,
            "referenced_columns": ref_columns,
            "update_rule": update_rule,
            "delete_rule": delete_rule,
        }


# ============================================================================
# BaseComparer Tests
# ============================================================================

class TestBaseComparer:
    """Tests for BaseComparer abstract methods and utilities"""

    @pytest.fixture
    def table_comparer(
        self, mock_source_connection, mock_target_connection, default_options
    ) -> TableComparer:
        """Use TableComparer to test BaseComparer functionality"""
        return TableComparer(
            mock_source_connection,
            mock_target_connection,
            default_options,
            "test-comparison-id"
        )

    def test_fix_order_respects_dependencies(self, table_comparer: TableComparer):
        """Fix order should respect database object dependencies"""
        # Tables should come before columns/constraints/indexes
        assert table_comparer.get_fix_order() == 2

    def test_should_compare_object_respects_schema_filters(
        self, mock_source_connection, mock_target_connection
    ):
        """should_compare_object should respect included/excluded schemas"""
        options = ComparisonOptions(
            included_schemas=["production"],
            excluded_schemas=["test"]
        )
        comparer = TableComparer(
            mock_source_connection,
            mock_target_connection,
            options,
            "test-id"
        )

        assert comparer.should_compare_object("production", "users") is True
        assert comparer.should_compare_object("staging", "users") is False
        assert comparer.should_compare_object("test", "users") is False

    def test_should_compare_object_respects_table_filters(
        self, mock_source_connection, mock_target_connection
    ):
        """should_compare_object should respect included/excluded tables"""
        options = ComparisonOptions(
            included_tables=["users", "orders"],
            excluded_tables=["audit_logs"]
        )
        comparer = TableComparer(
            mock_source_connection,
            mock_target_connection,
            options,
            "test-id"
        )

        assert comparer.should_compare_object("app", "users") is True
        assert comparer.should_compare_object("app", "orders") is True
        assert comparer.should_compare_object("app", "products") is False
        assert comparer.should_compare_object("app", "audit_logs") is False

    def test_determine_severity_for_critical_types(self, table_comparer: TableComparer):
        """Critical diff types should have CRITICAL severity"""
        assert table_comparer.determine_severity(
            DiffType.TABLE_MISSING_TARGET
        ) == SeverityLevel.CRITICAL
        assert table_comparer.determine_severity(
            DiffType.COLUMN_REMOVED
        ) == SeverityLevel.CRITICAL

    def test_determine_severity_for_high_types(self, table_comparer: TableComparer):
        """High priority diff types should have HIGH severity"""
        assert table_comparer.determine_severity(
            DiffType.COLUMN_TYPE_CHANGED
        ) == SeverityLevel.HIGH
        assert table_comparer.determine_severity(
            DiffType.INDEX_MISSING_TARGET
        ) == SeverityLevel.HIGH

    def test_create_missing_difference_for_source(self, table_comparer: TableComparer):
        """Should create correct difference for object missing in source"""
        obj_data = {
            "schema_name": "test",
            "table_name": "users",
            "constraint_name": None,
        }

        diff = table_comparer.create_missing_difference("test.users", obj_data, "source")

        assert diff.diff_type == DiffType.TABLE_MISSING_SOURCE
        assert diff.severity == SeverityLevel.HIGH
        assert diff.can_auto_fix is True

    def test_create_missing_difference_for_target(self, table_comparer: TableComparer):
        """Should create correct difference for object missing in target"""
        obj_data = {
            "schema_name": "test",
            "table_name": "users",
            "constraint_name": None,
        }

        diff = table_comparer.create_missing_difference("test.users", obj_data, "target")

        assert diff.diff_type == DiffType.TABLE_MISSING_TARGET
        assert diff.severity == SeverityLevel.HIGH
        assert diff.source_value == obj_data
        assert diff.target_value is None

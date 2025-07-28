from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum


class DiffType(str, Enum):
    """Types of differences that can be detected"""
    # Schema level
    SCHEMA_MISSING_SOURCE = "schema_missing_source"
    SCHEMA_MISSING_TARGET = "schema_missing_target"
    
    # Table level
    TABLE_MISSING_SOURCE = "table_missing_source"
    TABLE_MISSING_TARGET = "table_missing_target"
    
    # Column level
    COLUMN_ADDED = "column_added"
    COLUMN_REMOVED = "column_removed"
    COLUMN_TYPE_CHANGED = "column_type_changed"
    COLUMN_DEFAULT_CHANGED = "column_default_changed"
    COLUMN_NULLABLE_CHANGED = "column_nullable_changed"
    COLUMN_EXTRA_CHANGED = "column_extra_changed"
    
    # Index level
    INDEX_MISSING_SOURCE = "index_missing_source"
    INDEX_MISSING_TARGET = "index_missing_target"
    INDEX_COLUMNS_CHANGED = "index_columns_changed"
    INDEX_TYPE_CHANGED = "index_type_changed"
    INDEX_UNIQUE_CHANGED = "index_unique_changed"
    
    # Constraint level
    CONSTRAINT_MISSING_SOURCE = "constraint_missing_source"
    CONSTRAINT_MISSING_TARGET = "constraint_missing_target"
    CONSTRAINT_DEFINITION_CHANGED = "constraint_definition_changed"
    
    # Procedure/Function level
    ROUTINE_MISSING_SOURCE = "routine_missing_source"
    ROUTINE_MISSING_TARGET = "routine_missing_target"
    ROUTINE_DEFINITION_CHANGED = "routine_definition_changed"
    
    # View level
    VIEW_MISSING_SOURCE = "view_missing_source"
    VIEW_MISSING_TARGET = "view_missing_target"
    VIEW_DEFINITION_CHANGED = "view_definition_changed"
    
    # Trigger level
    TRIGGER_MISSING_SOURCE = "trigger_missing_source"
    TRIGGER_MISSING_TARGET = "trigger_missing_target"
    TRIGGER_DEFINITION_CHANGED = "trigger_definition_changed"


class SeverityLevel(str, Enum):
    """Severity levels for differences"""
    CRITICAL = "critical"  # Data loss risk
    HIGH = "high"         # Functionality impact
    MEDIUM = "medium"     # Performance impact
    LOW = "low"           # Cosmetic changes
    INFO = "info"         # Informational only


class ObjectType(str, Enum):
    """Database object types"""
    SCHEMA = "schema"
    TABLE = "table"
    COLUMN = "column"
    INDEX = "index"
    CONSTRAINT = "constraint"
    PROCEDURE = "procedure"
    FUNCTION = "function"
    VIEW = "view"
    TRIGGER = "trigger"
    EVENT = "event"


class DatabaseConfig(BaseModel):
    """Database connection configuration"""
    host: str
    port: int = 3306
    user: str
    password: str
    database: Optional[str] = None
    
    def get_connection_url(self, database: Optional[str] = None) -> str:
        """Generate SQLAlchemy connection URL"""
        db = database or self.database or ""
        return f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{db}"


class ComparisonOptions(BaseModel):
    """Options for database comparison"""
    compare_tables: bool = True
    compare_columns: bool = True
    compare_indexes: bool = True
    compare_constraints: bool = True
    compare_procedures: bool = True
    compare_functions: bool = True
    compare_views: bool = True
    compare_triggers: bool = True
    compare_events: bool = False
    
    included_schemas: Optional[List[str]] = None
    excluded_schemas: Optional[List[str]] = None
    included_tables: Optional[List[str]] = None
    excluded_tables: Optional[List[str]] = None
    
    ignore_auto_increment: bool = True
    ignore_comments: bool = False
    ignore_charset: bool = False
    ignore_collation: bool = False
    
    case_sensitive: bool = True
    
    
class Difference(BaseModel):
    """Represents a single difference between databases"""
    diff_type: DiffType
    severity: SeverityLevel
    object_type: ObjectType
    schema_name: Optional[str] = None
    object_name: str
    sub_object_name: Optional[str] = None  # For columns, indexes, etc.
    source_value: Optional[Any] = None
    target_value: Optional[Any] = None
    description: str
    
    # Additional metadata
    can_auto_fix: bool = False
    fix_order: int = 0  # For dependency ordering
    warnings: List[str] = Field(default_factory=list)
    
    
class ComparisonProgress(BaseModel):
    """Real-time progress update"""
    comparison_id: str
    phase: Literal["discovery", "comparison", "analysis", "report"]
    current: int
    total: int
    current_object: Optional[str] = None
    estimated_time_remaining: Optional[int] = None  # seconds
    message: Optional[str] = None
    

class ComparisonResult(BaseModel):
    """Complete comparison result"""
    comparison_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    source_config: DatabaseConfig
    target_config: DatabaseConfig
    options: ComparisonOptions
    
    differences: List[Difference]
    summary: Dict[str, Any]
    
    # Performance metrics
    duration_seconds: Optional[float] = None
    objects_compared: int = 0
    
    # Error handling
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    
    
class ComparisonProfile(BaseModel):
    """Saved comparison profile"""
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    source_config: DatabaseConfig
    target_config: DatabaseConfig
    comparison_options: ComparisonOptions
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    last_run: Optional[datetime] = None
    
    # Scheduling
    schedule_enabled: bool = False
    schedule_cron: Optional[str] = None
    
    # Notifications
    notification_email: Optional[str] = None
    notification_webhook: Optional[str] = None
    notify_on_differences: bool = True
    notify_on_errors: bool = True


class SyncScript(BaseModel):
    """Generated synchronization script"""
    comparison_id: str
    forward_script: str  # Source -> Target
    rollback_script: str  # Undo changes
    warnings: List[str]
    estimated_impact: Dict[str, Any]
    
    # Execution metadata
    estimated_duration: Optional[int] = None  # seconds
    requires_downtime: bool = False
    data_loss_risk: bool = False
    
    # Validation
    validated: bool = False
    validation_errors: List[str] = Field(default_factory=list)
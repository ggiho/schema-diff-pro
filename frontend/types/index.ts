export interface DatabaseConfig {
  host: string
  port: number
  user: string
  password: string
  database?: string
}

export interface ComparisonOptions {
  compare_tables: boolean
  compare_columns: boolean
  compare_indexes: boolean
  compare_constraints: boolean
  compare_procedures: boolean
  compare_functions: boolean
  compare_views: boolean
  compare_triggers: boolean
  compare_events: boolean
  included_schemas?: string[]
  excluded_schemas?: string[]
  included_tables?: string[]
  excluded_tables?: string[]
  ignore_auto_increment: boolean
  ignore_comments: boolean
  ignore_charset: boolean
  ignore_collation: boolean
  case_sensitive: boolean
}

export enum DiffType {
  SCHEMA_MISSING_SOURCE = "schema_missing_source",
  SCHEMA_MISSING_TARGET = "schema_missing_target",
  TABLE_MISSING_SOURCE = "table_missing_source",
  TABLE_MISSING_TARGET = "table_missing_target",
  COLUMN_ADDED = "column_added",
  COLUMN_REMOVED = "column_removed",
  COLUMN_TYPE_CHANGED = "column_type_changed",
  COLUMN_DEFAULT_CHANGED = "column_default_changed",
  COLUMN_NULLABLE_CHANGED = "column_nullable_changed",
  COLUMN_EXTRA_CHANGED = "column_extra_changed",
  INDEX_MISSING_SOURCE = "index_missing_source",
  INDEX_MISSING_TARGET = "index_missing_target",
  INDEX_COLUMNS_CHANGED = "index_columns_changed",
  INDEX_TYPE_CHANGED = "index_type_changed",
  INDEX_UNIQUE_CHANGED = "index_unique_changed",
  CONSTRAINT_MISSING_SOURCE = "constraint_missing_source",
  CONSTRAINT_MISSING_TARGET = "constraint_missing_target",
  CONSTRAINT_DEFINITION_CHANGED = "constraint_definition_changed",
  ROUTINE_MISSING_SOURCE = "routine_missing_source",
  ROUTINE_MISSING_TARGET = "routine_missing_target",
  ROUTINE_DEFINITION_CHANGED = "routine_definition_changed",
  VIEW_MISSING_SOURCE = "view_missing_source",
  VIEW_MISSING_TARGET = "view_missing_target",
  VIEW_DEFINITION_CHANGED = "view_definition_changed",
  TRIGGER_MISSING_SOURCE = "trigger_missing_source",
  TRIGGER_MISSING_TARGET = "trigger_missing_target",
  TRIGGER_DEFINITION_CHANGED = "trigger_definition_changed",
}

export enum SeverityLevel {
  CRITICAL = "critical",
  HIGH = "high",
  MEDIUM = "medium",
  LOW = "low",
  INFO = "info",
}

export enum ObjectType {
  SCHEMA = "schema",
  TABLE = "table",
  COLUMN = "column",
  INDEX = "index",
  CONSTRAINT = "constraint",
  PROCEDURE = "procedure",
  FUNCTION = "function",
  VIEW = "view",
  TRIGGER = "trigger",
  EVENT = "event",
}

export interface Difference {
  diff_type: DiffType
  severity: SeverityLevel
  object_type: ObjectType
  schema_name?: string
  object_name: string
  sub_object_name?: string
  source_value?: any
  target_value?: any
  description: string
  can_auto_fix: boolean
  fix_order: number
  warnings: string[]
}

export interface ComparisonProgress {
  comparison_id: string
  phase: "discovery" | "comparison" | "analysis" | "report"
  current: number
  total: number
  current_object?: string
  estimated_time_remaining?: number
  message?: string
}

export interface ComparisonResult {
  comparison_id: string
  started_at: string
  completed_at?: string
  source_config: DatabaseConfig
  target_config: DatabaseConfig
  options: ComparisonOptions
  differences: Difference[]
  summary: {
    total_differences: number
    by_severity: Record<string, number>
    by_type: Record<string, number>
    by_object_type: Record<string, number>
    critical_count: number
    can_auto_fix: number
    data_loss_risks: any[]
    schemas_affected: string[]
    tables_affected: string[]
    total_objects_compared: number
  }
  duration_seconds?: number
  objects_compared: number
  errors: string[]
  warnings: string[]
}

export interface SyncScript {
  comparison_id: string
  forward_script: string
  rollback_script: string
  warnings: string[]
  estimated_impact: any
  estimated_duration?: number
  requires_downtime: boolean
  data_loss_risk: boolean
  validated: boolean
  validation_errors: string[]
}
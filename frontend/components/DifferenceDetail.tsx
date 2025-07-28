'use client'

import { Difference, ObjectType, DiffType } from '@/types'
import { 
  Database, Table, Key, Index, 
  ArrowRight, Code, Copy, CheckCircle,
  AlertTriangle, Plus, Minus, Edit,
  FileText
} from 'lucide-react'
import { Button } from './ui/button'
import { toast } from 'react-hot-toast'

interface DifferenceDetailProps {
  difference: Difference
}

export function DifferenceDetail({ difference }: DifferenceDetailProps) {
  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    toast.success('Copied to clipboard')
  }

  const formatValue = (value: any, type: ObjectType) => {
    if (!value) return null

    switch (type) {
      case ObjectType.COLUMN:
        return formatColumnValue(value)
      case ObjectType.INDEX:
        return formatIndexValue(value)
      case ObjectType.CONSTRAINT:
        return formatConstraintValue(value)
      case ObjectType.TABLE:
        return formatTableValue(value)
      default:
        return formatGenericValue(value)
    }
  }

  const formatColumnValue = (value: any) => {
    if (typeof value === 'string') return value

    return (
      <div className="space-y-2">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <span className="text-xs font-medium text-muted-foreground">Type:</span>
            <p className="text-sm font-mono">{value.column_type || value.data_type}</p>
          </div>
          <div>
            <span className="text-xs font-medium text-muted-foreground">Nullable:</span>
            <p className="text-sm">{value.is_nullable ? 'YES' : 'NO'}</p>
          </div>
        </div>
        {value.column_default && (
          <div>
            <span className="text-xs font-medium text-muted-foreground">Default:</span>
            <p className="text-sm font-mono">{value.column_default}</p>
          </div>
        )}
        {value.extra && (
          <div>
            <span className="text-xs font-medium text-muted-foreground">Extra:</span>
            <p className="text-sm">{value.extra}</p>
          </div>
        )}
      </div>
    )
  }

  const formatIndexValue = (value: any) => {
    if (typeof value === 'string') return value

    return (
      <div className="space-y-2">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <span className="text-xs font-medium text-muted-foreground">Type:</span>
            <p className="text-sm">{value.index_type}</p>
          </div>
          <div>
            <span className="text-xs font-medium text-muted-foreground">Unique:</span>
            <p className="text-sm">{value.is_unique ? 'YES' : 'NO'}</p>
          </div>
        </div>
        <div>
          <span className="text-xs font-medium text-muted-foreground">Columns:</span>
          <p className="text-sm font-mono">{value.columns}</p>
        </div>
      </div>
    )
  }

  const formatConstraintValue = (value: any) => {
    if (typeof value === 'string') return value

    return (
      <div className="space-y-2">
        <div>
          <span className="text-xs font-medium text-muted-foreground">Type:</span>
          <p className="text-sm">{value.constraint_type}</p>
        </div>
        {value.columns && (
          <div>
            <span className="text-xs font-medium text-muted-foreground">Columns:</span>
            <p className="text-sm font-mono">{value.columns}</p>
          </div>
        )}
        {value.referenced_table_name && (
          <div>
            <span className="text-xs font-medium text-muted-foreground">References:</span>
            <p className="text-sm font-mono">
              {value.referenced_table_schema}.{value.referenced_table_name}
              ({value.referenced_columns})
            </p>
          </div>
        )}
        {(value.update_rule || value.delete_rule) && (
          <div className="grid grid-cols-2 gap-4">
            {value.update_rule && (
              <div>
                <span className="text-xs font-medium text-muted-foreground">On Update:</span>
                <p className="text-sm">{value.update_rule}</p>
              </div>
            )}
            {value.delete_rule && (
              <div>
                <span className="text-xs font-medium text-muted-foreground">On Delete:</span>
                <p className="text-sm">{value.delete_rule}</p>
              </div>
            )}
          </div>
        )}
      </div>
    )
  }

  const formatTableValue = (value: any) => {
    if (typeof value === 'string') return value

    return (
      <div className="space-y-2">
        {value.engine && (
          <div>
            <span className="text-xs font-medium text-muted-foreground">Engine:</span>
            <p className="text-sm">{value.engine}</p>
          </div>
        )}
        {value.collation && (
          <div>
            <span className="text-xs font-medium text-muted-foreground">Collation:</span>
            <p className="text-sm font-mono">{value.collation}</p>
          </div>
        )}
      </div>
    )
  }

  const formatGenericValue = (value: any) => {
    if (typeof value === 'string') {
      return <p className="text-sm font-mono">{value}</p>
    }
    return (
      <pre className="text-xs font-mono text-muted-foreground overflow-x-auto">
        {JSON.stringify(value, null, 2)}
      </pre>
    )
  }

  const getDiffTypeIcon = () => {
    if (difference.diff_type.includes('MISSING_TARGET') || difference.diff_type.includes('ADDED')) {
      return <Plus className="h-4 w-4 text-green-600" />
    }
    if (difference.diff_type.includes('MISSING_SOURCE') || difference.diff_type.includes('REMOVED')) {
      return <Minus className="h-4 w-4 text-red-600" />
    }
    return <Edit className="h-4 w-4 text-blue-600" />
  }

  const getDiffTypeLabel = () => {
    if (difference.diff_type.includes('MISSING_TARGET') || difference.diff_type.includes('REMOVED')) {
      return 'Source Only'
    }
    if (difference.diff_type.includes('MISSING_SOURCE') || difference.diff_type.includes('ADDED')) {
      return 'Target Only'
    }
    return 'Modified'
  }
  
  const getSourceLabel = () => {
    const diffLabel = getDiffTypeLabel()
    if (diffLabel === 'Source Only') {
      return 'Exists only in source'
    }
    if (diffLabel === 'Modified') {
      return 'Current value in source'
    }
    return null
  }
  
  const getTargetLabel = () => {
    const diffLabel = getDiffTypeLabel()
    if (diffLabel === 'Target Only') {
      return 'Exists only in target'
    }
    if (diffLabel === 'Modified') {
      return 'Current value in target'
    }
    return null
  }

  const generateOption1SQL = () => {
    const tableName = `\`${difference.schema_name}\`.\`${difference.object_name}\``
    const columnName = difference.sub_object_name ? `\`${difference.sub_object_name}\`` : ''
    
    switch (difference.diff_type) {
      case DiffType.COLUMN_ADDED:
        // Target Only: Option 1 = Add to Source
        if (difference.target_value) {
          if (typeof difference.target_value === 'string') {
            return `-- Execute on SOURCE database:\nALTER TABLE ${tableName} ADD COLUMN ${columnName} ${difference.target_value};`
          }
          const col = difference.target_value
          const columnType = col.column_type || col.data_type
          if (columnType) {
            const nullable = col.is_nullable !== undefined ? (col.is_nullable ? 'NULL' : 'NOT NULL') : ''
            const defaultValue = col.column_default ? ` DEFAULT ${col.column_default}` : ''
            const extra = col.extra ? ` ${col.extra}` : ''
            return `-- Execute on SOURCE database:\nALTER TABLE ${tableName} ADD COLUMN ${columnName} ${columnType} ${nullable}${defaultValue}${extra};`
          }
        }
        return `-- Execute on SOURCE database:\nALTER TABLE ${tableName} ADD COLUMN ${columnName} VARCHAR(255) NULL;`
        
      case DiffType.COLUMN_REMOVED:
        // Source Only: Option 1 = Remove from Source
        return `-- Execute on SOURCE database:\nALTER TABLE ${tableName} DROP COLUMN ${columnName};`
        
      case DiffType.COLUMN_TYPE_CHANGED:
        if (difference.target_value) {
          // If target_value is a string, it's the column type directly
          if (typeof difference.target_value === 'string') {
            return `ALTER TABLE ${tableName} MODIFY COLUMN ${columnName} ${difference.target_value};`
          }
          
          // If it's an object, extract the column type and other properties
          const col = difference.target_value
          const columnType = col.column_type || col.data_type
          if (columnType) {
            const nullable = col.is_nullable !== undefined ? (col.is_nullable ? 'NULL' : 'NOT NULL') : ''
            const defaultValue = col.column_default ? ` DEFAULT ${col.column_default}` : ''
            const extra = col.extra ? ` ${col.extra}` : ''
            return `ALTER TABLE ${tableName} MODIFY COLUMN ${columnName} ${columnType} ${nullable}${defaultValue}${extra};`
          }
        }
        return `-- Unable to determine target column type`
        
      case DiffType.INDEX_MISSING_TARGET:
        // Source Only: Option 1 = Remove from Source
        return `-- Execute on SOURCE database:\nDROP INDEX ${columnName} ON ${tableName};`
        
      case DiffType.INDEX_MISSING_SOURCE:
        // Target Only: Option 1 = Add to Source
        if (difference.target_value) {
          const idx = difference.target_value
          const unique = idx.is_unique ? 'UNIQUE ' : ''
          let columns = idx.columns
          
          if (Array.isArray(columns)) {
            columns = columns.join(', ')
          }
          
          if (!columns) {
            columns = '-- column_name --'
          }
          
          const indexType = idx.index_type && idx.index_type !== 'BTREE' ? ` USING ${idx.index_type}` : ''
          return `-- Execute on SOURCE database:\nCREATE ${unique}INDEX ${columnName} ON ${tableName} (${columns})${indexType};`
        }
        return `-- Execute on SOURCE database:\nCREATE INDEX ${columnName} ON ${tableName} (-- column_name --);`
        
      case DiffType.CONSTRAINT_MISSING_TARGET:
        if (difference.target_value) {
          const const_data = difference.target_value
          const constraintType = const_data.constraint_type
          
          if (constraintType === 'FOREIGN KEY') {
            const columns = const_data.columns || 'column_name'
            const refTable = `\`${const_data.referenced_table_schema}\`.\`${const_data.referenced_table_name}\``
            const refColumns = const_data.referenced_columns || 'ref_column'
            const updateRule = const_data.update_rule || 'RESTRICT'
            const deleteRule = const_data.delete_rule || 'RESTRICT'
            return `ALTER TABLE ${tableName} ADD CONSTRAINT ${columnName} FOREIGN KEY (${columns}) REFERENCES ${refTable} (${refColumns}) ON UPDATE ${updateRule} ON DELETE ${deleteRule};`
          } else if (constraintType === 'PRIMARY KEY') {
            const columns = const_data.columns || 'column_name'
            return `ALTER TABLE ${tableName} ADD PRIMARY KEY (${columns});`
          } else if (constraintType === 'UNIQUE') {
            const columns = const_data.columns || 'column_name'
            return `ALTER TABLE ${tableName} ADD CONSTRAINT ${columnName} UNIQUE (${columns});`
          }
        }
        return `ALTER TABLE ${tableName} ADD CONSTRAINT ${columnName} ...;`
        
      case DiffType.CONSTRAINT_MISSING_SOURCE:
        return `ALTER TABLE ${tableName} DROP CONSTRAINT ${columnName};`
        
      case DiffType.TABLE_MISSING_TARGET:
        // Source Only: Option 1 = Delete from Source
        return `-- Execute on SOURCE database:\nDROP TABLE IF EXISTS ${tableName};`
        
      case DiffType.TABLE_MISSING_SOURCE:
        // Target Only: Option 1 = Add to Source  
        if (difference.target_value) {
          const table = difference.target_value
          const engine = table.engine ? ` ENGINE=${table.engine}` : ' ENGINE=InnoDB'
          const collation = table.collation ? ` COLLATE=${table.collation}` : ''
          return `-- Execute on SOURCE database:\nCREATE TABLE ${tableName} (\n  -- Table structure will be generated in sync script\n)${engine}${collation};`
        }
        return `-- Execute on SOURCE database:\nCREATE TABLE ${tableName} (\n  -- Table structure will be generated in sync script\n) ENGINE=InnoDB;`
        
      default:
        return `-- Forward SQL for ${difference.diff_type} will be generated in sync script`
    }
  }

  const getOption1Label = () => {
    const diffType = difference.diff_type.toLowerCase()
    if (diffType.includes('missing_target')) {
      return 'Option 1: Remove from Source'
    }
    if (diffType.includes('missing_source')) {
      return 'Option 1: Add to Source'  
    }
    return 'Option 1'
  }

  const getOption2Label = () => {
    const diffType = difference.diff_type.toLowerCase()
    if (diffType.includes('missing_target')) {
      return 'Option 2: Add to Target'
    }
    if (diffType.includes('missing_source')) {
      return 'Option 2: Remove from Target'
    }
    return 'Option 2'
  }

  const generateOption2SQL = () => {
    const tableName = `\`${difference.schema_name}\`.\`${difference.object_name}\``
    const columnName = difference.sub_object_name ? `\`${difference.sub_object_name}\`` : ''
    
    switch (difference.diff_type) {
      case DiffType.COLUMN_ADDED:
        // Target Only: Option 2 = Remove from Target
        return `-- Execute on TARGET database:\nALTER TABLE ${tableName} DROP COLUMN ${columnName};`
        
      case DiffType.COLUMN_REMOVED:
        // Source Only: Option 2 = Add to Target
        if (difference.source_value) {
          if (typeof difference.source_value === 'string') {
            return `-- Execute on TARGET database:\nALTER TABLE ${tableName} ADD COLUMN ${columnName} ${difference.source_value};`
          }
          const col = difference.source_value
          const columnType = col.column_type || col.data_type
          if (columnType) {
            const nullable = col.is_nullable !== undefined ? (col.is_nullable ? 'NULL' : 'NOT NULL') : ''
            const defaultValue = col.column_default ? ` DEFAULT ${col.column_default}` : ''
            const extra = col.extra ? ` ${col.extra}` : ''
            return `-- Execute on TARGET database:\nALTER TABLE ${tableName} ADD COLUMN ${columnName} ${columnType} ${nullable}${defaultValue}${extra};`
          }
        }
        return `-- Execute on TARGET database:\nALTER TABLE ${tableName} ADD COLUMN ${columnName} VARCHAR(255) NULL;`
        
      case DiffType.COLUMN_TYPE_CHANGED:
        if (difference.source_value) {
          // If source_value is a string, it's the column type directly
          if (typeof difference.source_value === 'string') {
            return `ALTER TABLE ${tableName} MODIFY COLUMN ${columnName} ${difference.source_value};`
          }
          
          // If it's an object, extract the column type and other properties
          const col = difference.source_value
          const columnType = col.column_type || col.data_type
          if (columnType) {
            const nullable = col.is_nullable !== undefined ? (col.is_nullable ? 'NULL' : 'NOT NULL') : ''
            const defaultValue = col.column_default ? ` DEFAULT ${col.column_default}` : ''
            const extra = col.extra ? ` ${col.extra}` : ''
            return `ALTER TABLE ${tableName} MODIFY COLUMN ${columnName} ${columnType} ${nullable}${defaultValue}${extra};`
          }
        }
        return `-- Unable to determine source column type`
        
      case DiffType.INDEX_MISSING_TARGET:
        // Source Only: Option 2 = Add to Target
        if (difference.source_value) {
          const idx = difference.source_value
          const unique = idx.is_unique ? 'UNIQUE ' : ''
          let columns = idx.columns
          
          if (Array.isArray(columns)) {
            columns = columns.join(', ')
          }
          
          if (!columns) {
            columns = '-- column_name --'
          }
          
          const indexType = idx.index_type && idx.index_type !== 'BTREE' ? ` USING ${idx.index_type}` : ''
          return `-- Execute on TARGET database:\nCREATE ${unique}INDEX ${columnName} ON ${tableName} (${columns})${indexType};`
        }
        return `-- Execute on TARGET database:\nCREATE INDEX ${columnName} ON ${tableName} (-- column_name --);`
        
      case DiffType.INDEX_MISSING_SOURCE:
        // Target Only: Option 2 = Remove from Target
        return `-- Execute on TARGET database:\nDROP INDEX ${columnName} ON ${tableName};`
        
      case DiffType.CONSTRAINT_MISSING_TARGET:
        return `ALTER TABLE ${tableName} DROP CONSTRAINT ${columnName};`
        
      case DiffType.CONSTRAINT_MISSING_SOURCE:
        if (difference.source_value) {
          const const_data = difference.source_value
          const constraintType = const_data.constraint_type
          
          if (constraintType === 'FOREIGN KEY') {
            const columns = const_data.columns || 'column_name'
            const refTable = `\`${const_data.referenced_table_schema}\`.\`${const_data.referenced_table_name}\``
            const refColumns = const_data.referenced_columns || 'ref_column'
            const updateRule = const_data.update_rule || 'RESTRICT'
            const deleteRule = const_data.delete_rule || 'RESTRICT'
            return `ALTER TABLE ${tableName} ADD CONSTRAINT ${columnName} FOREIGN KEY (${columns}) REFERENCES ${refTable} (${refColumns}) ON UPDATE ${updateRule} ON DELETE ${deleteRule};`
          } else if (constraintType === 'PRIMARY KEY') {
            const columns = const_data.columns || 'column_name'
            return `ALTER TABLE ${tableName} ADD PRIMARY KEY (${columns});`
          } else if (constraintType === 'UNIQUE') {
            const columns = const_data.columns || 'column_name'
            return `ALTER TABLE ${tableName} ADD CONSTRAINT ${columnName} UNIQUE (${columns});`
          }
        }
        return `-- ADD CONSTRAINT ${columnName} with original definition;`
        
      case DiffType.TABLE_MISSING_TARGET:
        // Source Only: Option 2 = Add to Target
        if (difference.source_value) {
          const table = difference.source_value
          const engine = table.engine ? ` ENGINE=${table.engine}` : ' ENGINE=InnoDB'
          const collation = table.collation ? ` COLLATE=${table.collation}` : ''
          return `-- Execute on TARGET database:\nCREATE TABLE ${tableName} (\n  -- Table structure will be generated in sync script\n)${engine}${collation};`
        }
        return `-- Execute on TARGET database:\nCREATE TABLE ${tableName} (\n  -- Table structure will be generated in sync script\n) ENGINE=InnoDB;`
        
      case DiffType.TABLE_MISSING_SOURCE:
        // Target Only: Option 2 = Delete from Target
        return `-- Execute on TARGET database:\nDROP TABLE IF EXISTS ${tableName};`
        
      default:
        return `-- Rollback SQL for ${difference.diff_type} will be generated in sync script`
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        {getDiffTypeIcon()}
        <div>
          <p className="font-medium capitalize">{difference.object_type.replace('_', ' ')}</p>
          <p className="text-sm text-muted-foreground">
            {getDiffTypeLabel()}
          </p>
        </div>
      </div>

      {/* Values Comparison */}
      {(difference.source_value || difference.target_value) && (
        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            {/* Source Value */}
            {difference.source_value && (
              <div className="rounded-lg border border-blue-200 bg-blue-50/50 p-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Database className="h-4 w-4 text-blue-600" />
                    <span className="text-sm font-medium text-blue-900">Source Database</span>
                  </div>
                  <span className="text-xs text-blue-700">{getSourceLabel()}</span>
                </div>
                {formatValue(difference.source_value, difference.object_type)}
              </div>
            )}

            {/* Target Value */}
            {difference.target_value && (
              <div className="rounded-lg border border-gray-200 bg-gray-50/50 p-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Database className="h-4 w-4 text-gray-600" />
                    <span className="text-sm font-medium text-gray-900">Target Database</span>
                  </div>
                  <span className="text-xs text-gray-700">{getTargetLabel()}</span>
                </div>
                {formatValue(difference.target_value, difference.object_type)}
              </div>
            )}
          </div>

          {/* Arrow for changes */}
          {difference.source_value && difference.target_value && (
            <div className="flex justify-center">
              <ArrowRight className="h-5 w-5 text-muted-foreground" />
            </div>
          )}
        </div>
      )}

      {/* SQL Preview */}
      <div className="space-y-3">
        {/* Forward SQL */}
        <div className="rounded-lg border bg-card p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Code className="h-4 w-4" />
              <span className="text-sm font-medium">{getOption1Label()}</span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => copyToClipboard(generateOption1SQL())}
            >
              <Copy className="h-3 w-3" />
            </Button>
          </div>
          <pre className="text-xs font-mono bg-muted p-2 rounded overflow-x-auto">
            {generateOption1SQL()}
          </pre>
        </div>

        {/* Rollback SQL */}
        <div className="rounded-lg border bg-card p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Code className="h-4 w-4" />
              <span className="text-sm font-medium">{getOption2Label()}</span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => copyToClipboard(generateOption2SQL())}
            >
              <Copy className="h-3 w-3" />
            </Button>
          </div>
          <pre className="text-xs font-mono bg-muted p-2 rounded overflow-x-auto">
            {generateOption2SQL()}
          </pre>
        </div>
      </div>

      {/* Warnings */}
      {difference.warnings.length > 0 && (
        <div className="rounded-lg border border-yellow-200 bg-yellow-50/50 p-3">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="h-4 w-4 text-yellow-600" />
            <span className="text-sm font-medium text-yellow-900">Warnings</span>
          </div>
          <ul className="space-y-1">
            {difference.warnings.map((warning, i) => (
              <li key={i} className="text-sm text-yellow-800 flex items-start gap-2">
                <span className="w-1 h-1 bg-yellow-600 rounded-full mt-2 flex-shrink-0" />
                {warning}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Auto-fix indicator */}
      {difference.can_auto_fix && (
        <div className="flex items-center gap-2 text-sm text-green-700">
          <CheckCircle className="h-4 w-4" />
          <span>This difference can be automatically fixed in the sync script</span>
        </div>
      )}
    </div>
  )
}
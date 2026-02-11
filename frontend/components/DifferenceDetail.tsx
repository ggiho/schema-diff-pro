'use client'

import { Difference, ObjectType, DiffType } from '@/types'
import { 
  Database, 
  ArrowRight, Code, Copy, CheckCircle,
  AlertTriangle, Plus, Minus, Edit
} from 'lucide-react'
import { Button } from './ui/button'
import { toast } from 'react-hot-toast'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

interface DifferenceDetailProps {
  difference: Difference
}

// Escape string value for safe SQL interpolation
const escapeSqlString = (value: string): string => {
  return value.replace(/\\/g, '\\\\').replace(/'/g, "''")
}

export function DifferenceDetail({ difference }: DifferenceDetailProps) {
  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    toast.success('Copied to clipboard')
  }

  // Build complete column definition preserving all attributes (COMMENT, DEFAULT, etc.)
  const buildColumnDefinition = (
    colInfo: any, 
    overrideType?: string, 
    overrideNullable?: boolean
  ): string => {
    if (!colInfo || typeof colInfo !== 'object') {
      return colInfo ? String(colInfo) : 'VARCHAR(255)'
    }

    // Column type
    const colType = overrideType || colInfo.column_type || colInfo.data_type || 'VARCHAR(255)'

    // Character set (for text-based columns)
    const charset = colInfo.character_set
    const charsetClause = charset ? ` CHARACTER SET ${charset}` : ''

    // Collation (for text-based columns)
    const collation = colInfo.collation
    const collationClause = collation ? ` COLLATE ${collation}` : ''

    // Nullable
    let nullable: string
    if (overrideNullable !== undefined) {
      nullable = overrideNullable ? 'NULL' : 'NOT NULL'
    } else {
      nullable = colInfo.is_nullable ? 'NULL' : 'NOT NULL'
    }

    // Default value
    let defaultClause = ''
    const defaultVal = colInfo.column_default
    if (defaultVal !== null && defaultVal !== undefined) {
      const defaultStr = String(defaultVal).toUpperCase()
      if (defaultStr === 'CURRENT_TIMESTAMP' || defaultStr === 'CURRENT_DATE' || defaultStr === 'NULL' || defaultStr.startsWith('CURRENT_')) {
        defaultClause = ` DEFAULT ${defaultVal}`
      } else {
        defaultClause = ` DEFAULT '${escapeSqlString(String(defaultVal))}'`
      }
    }

    // Extra (AUTO_INCREMENT, ON UPDATE CURRENT_TIMESTAMP, etc.)
    let extraClause = ''
    if (colInfo.extra) {
      extraClause = ` ${colInfo.extra}`
    }

    // Comment - IMPORTANT: MySQL loses comment on MODIFY if not specified
    let commentClause = ''
    if (colInfo.comment) {
      const escapedComment = colInfo.comment.replace(/'/g, "''")
      commentClause = ` COMMENT '${escapedComment}'`
    }

    return `${colType}${charsetClause}${collationClause} ${nullable}${defaultClause}${extraClause}${commentClause}`.trim()
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
        {(value.character_set || value.collation) && (
          <div className="grid grid-cols-2 gap-4">
            {value.character_set && (
              <div>
                <span className="text-xs font-medium text-muted-foreground">Charset:</span>
                <p className="text-sm font-mono">{value.character_set}</p>
              </div>
            )}
            {value.collation && (
              <div>
                <span className="text-xs font-medium text-muted-foreground">Collation:</span>
                <p className="text-sm font-mono">{value.collation}</p>
              </div>
            )}
          </div>
        )}
        {value.column_default !== undefined && value.column_default !== null && (
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
        {value.comment && (
          <div>
            <span className="text-xs font-medium text-muted-foreground">Comment:</span>
            <p className="text-sm">{value.comment}</p>
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
        {value.partition_method && (
          <div>
            <span className="text-xs font-medium text-muted-foreground">Partition Method:</span>
            <p className="text-sm font-mono">{value.partition_method}</p>
          </div>
        )}
        {value.partition_expression && (
          <div>
            <span className="text-xs font-medium text-muted-foreground">Partition Expression:</span>
            <p className="text-sm font-mono">{value.partition_expression}</p>
          </div>
        )}
        {value.partitions && Object.keys(value.partitions).length > 0 && (
          <div>
            <span className="text-xs font-medium text-muted-foreground">Partitions:</span>
            <div className="mt-1 space-y-1">
              {Object.entries(value.partitions).map(([pName, pInfo]: [string, any]) => (
                <p key={pName} className="text-sm font-mono">
                  {pName}: {pInfo.description || '(no description)'}
                </p>
              ))}
            </div>
          </div>
        )}
        {value.name && value.description && (
          <div>
            <span className="text-xs font-medium text-muted-foreground">Partition:</span>
            <p className="text-sm font-mono">{value.name}: {value.description}</p>
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

  // Generate full CREATE TABLE SQL from table data
  const generateCreateTableSQL = (tableData: any, tableName: string, targetDb: 'SOURCE' | 'TARGET') => {
    if (!tableData || typeof tableData !== 'object') {
      return `-- Execute on ${targetDb} database:\nCREATE TABLE ${tableName} (\n  -- Table structure not available\n) ENGINE=InnoDB;`
    }

    const columns = tableData.columns
    const engine = tableData.engine || 'InnoDB'
    const collation = tableData.collation || ''

    if (!columns || typeof columns !== 'object' || Object.keys(columns).length === 0) {
      return `-- Execute on ${targetDb} database:\nCREATE TABLE ${tableName} (\n  -- Column information not available\n) ENGINE=${engine}${collation ? ` COLLATE=${collation}` : ''};`
    }

    // Sort columns by ordinal_position
    const sortedColumns = Object.entries(columns).sort((a: any, b: any) => {
      const posA = a[1]?.ordinal_position || 0
      const posB = b[1]?.ordinal_position || 0
      return posA - posB
    })

    const colDefs: string[] = []
    const primaryKeys: string[] = []

    for (const [colName, colInfo] of sortedColumns) {
      if (typeof colInfo !== 'object') continue

      const col = colInfo as any
      const colType = col.column_type || col.data_type || 'VARCHAR(255)'
      const nullable = col.is_nullable ? 'NULL' : 'NOT NULL'
      
      let defaultClause = ''
      if (col.column_default !== null && col.column_default !== undefined) {
        const defaultVal = col.column_default
        // Quote string defaults, but not expressions like CURRENT_TIMESTAMP
        if (typeof defaultVal === 'string' && !defaultVal.toUpperCase().startsWith('CURRENT_') && defaultVal.toUpperCase() !== 'NULL') {
          defaultClause = ` DEFAULT '${escapeSqlString(String(defaultVal))}'`
        } else {
          defaultClause = ` DEFAULT ${defaultVal}`
        }
      }

      let extra = ''
      if (col.extra && col.extra.toLowerCase().includes('auto_increment')) {
        extra = ' AUTO_INCREMENT'
      }

      colDefs.push(`\`${colName}\` ${colType} ${nullable}${defaultClause}${extra}`)

      // Track primary keys
      if (col.column_key === 'PRI') {
        primaryKeys.push(`\`${colName}\``)
      }
    }

    // Add PRIMARY KEY if exists
    if (primaryKeys.length > 0) {
      colDefs.push(`PRIMARY KEY (${primaryKeys.join(', ')})`)
    }

    const engineClause = engine ? ` ENGINE=${engine}` : ''
    const collationClause = collation ? ` COLLATE=${collation}` : ''

    return `-- Execute on ${targetDb} database:\nCREATE TABLE ${tableName} (\n  ${colDefs.join(',\n  ')}\n)${engineClause}${collationClause};`
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
    if (difference.diff_type.includes('DUPLICATE_SOURCE')) {
      return 'Duplicate in Source'
    }
    if (difference.diff_type.includes('DUPLICATE_TARGET')) {
      return 'Duplicate in Target'
    }
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
    if (diffLabel === 'Duplicate in Source') {
      return 'Original index (has same structure)'
    }
    if (diffLabel === 'Duplicate in Target') {
      return 'Original index structure'
    }
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
    if (diffLabel === 'Duplicate in Source') {
      return 'Index does not exist in target'
    }
    if (diffLabel === 'Duplicate in Target') {
      return 'Duplicate index (has same structure)'
    }
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
            let defaultValue = ''
            if (col.column_default !== undefined && col.column_default !== null) {
              const defVal = String(col.column_default).toUpperCase()
              if (defVal === 'CURRENT_TIMESTAMP' || defVal === 'CURRENT_DATE' || defVal === 'NULL' || defVal.startsWith('CURRENT_')) {
                defaultValue = ` DEFAULT ${col.column_default}`
              } else {
                defaultValue = ` DEFAULT '${escapeSqlString(String(col.column_default))}'`
              }
            }
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
          // Target → Source: Make Source like Target (use ALL of Target's attributes)
          const targetInfo = typeof difference.target_value === 'object' ? difference.target_value : null

          if (targetInfo) {
            const colDef = buildColumnDefinition(targetInfo)
            return `-- Execute on SOURCE database:\nALTER TABLE ${tableName} MODIFY COLUMN ${columnName} ${colDef};`
          }

          const targetType = typeof difference.target_value === 'string'
            ? difference.target_value
            : difference.target_value.column_type || difference.target_value.data_type
          return `-- Execute on SOURCE database:\nALTER TABLE ${tableName} MODIFY COLUMN ${columnName} ${targetType};`
        }
        return `-- Unable to determine target column type`
        
      case DiffType.COLUMN_NULLABLE_CHANGED:
        if (difference.target_value !== undefined) {
          // Target → Source: Make Source like Target (use ALL of Target's attributes)
          const targetInfo = typeof difference.target_value === 'object' ? difference.target_value : null

          if (targetInfo) {
            const colDef = buildColumnDefinition(targetInfo)
            return `-- Execute on SOURCE database:\nALTER TABLE ${tableName} MODIFY COLUMN ${columnName} ${colDef};`
          }

          const targetNullable = typeof difference.target_value === 'object'
            ? difference.target_value.is_nullable
            : difference.target_value
          const columnType = typeof difference.target_value === 'object'
            ? difference.target_value.column_type
            : 'VARCHAR(255)'
          const nullable = targetNullable ? 'NULL' : 'NOT NULL'

          return `-- Execute on SOURCE database:\nALTER TABLE ${tableName} MODIFY COLUMN ${columnName} ${columnType} ${nullable};`
        }
        return `-- Unable to determine target column info`
        
      case DiffType.COLUMN_DEFAULT_CHANGED:
        if (difference.target_value !== undefined) {
          // Target → Source: Make Source like Target (use Target's attributes)
          const targetInfo = typeof difference.target_value === 'object' ? difference.target_value : null

          if (targetInfo) {
            // Use full column definition with MODIFY COLUMN
            const colDef = buildColumnDefinition(targetInfo)
            return `-- Execute on SOURCE database:\nALTER TABLE ${tableName} MODIFY COLUMN ${columnName} ${colDef};`
          }

          // Fallback for primitive value
          if (difference.target_value === null) {
            return `-- Execute on SOURCE database:\nALTER TABLE ${tableName} ALTER COLUMN ${columnName} DROP DEFAULT;`
          } else {
            const defaultVal = String(difference.target_value)
            const quotedDefault = defaultVal.toUpperCase().startsWith('CURRENT_') || defaultVal.toUpperCase() === 'NULL'
              ? defaultVal
              : `'${defaultVal}'`
            return `-- Execute on SOURCE database:\nALTER TABLE ${tableName} ALTER COLUMN ${columnName} SET DEFAULT ${quotedDefault};`
          }
        }
        return `-- Unable to determine target default value`
      
      case DiffType.COLUMN_EXTRA_CHANGED:
        // Handle comment, charset, collation changes
        if (difference.target_value && typeof difference.target_value === 'object') {
          const targetInfo = difference.target_value
          const colDef = buildColumnDefinition(targetInfo)
          return `-- Execute on SOURCE database:\nALTER TABLE ${tableName} MODIFY COLUMN ${columnName} ${colDef};`
        }
        return `-- Execute on SOURCE database:\n-- Modify column extra properties\nALTER TABLE ${tableName} MODIFY COLUMN ${columnName} /* update properties */;`

      case DiffType.COLUMN_RENAMED:
        // Column renamed: Option 1 = Rename in Source to match Target
        // source_display_value = source name (desired), target_display_value = target name (current)
        if (difference.target_value && typeof difference.target_value === 'object') {
          const targetName = difference.target_display_value || 'target_name'
          const sourceName = difference.source_display_value || difference.sub_object_name
          const colDef = buildColumnDefinition(difference.target_value)
          return `-- Execute on SOURCE database:\n-- Rename column to match target\nALTER TABLE ${tableName} CHANGE COLUMN \`${sourceName}\` \`${targetName}\` ${colDef};`
        }
        return `-- Execute on SOURCE database:\nALTER TABLE ${tableName} CHANGE COLUMN ${columnName} \`new_name\` /* column definition */;`

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
      
      case DiffType.INDEX_RENAMED:
        // Index renamed: Option 1 = Rename in Source to match Target
        if (difference.target_value) {
          const targetName = difference.target_value.index_name
          return `-- Execute on SOURCE database:\n-- Rename index to match target\nALTER TABLE ${tableName} RENAME INDEX \`${difference.sub_object_name}\` TO \`${targetName}\`;`
        }
        return `-- Execute on SOURCE database:\nALTER TABLE ${tableName} RENAME INDEX \`${difference.sub_object_name}\` TO \`new_name\`;`
      
      case DiffType.INDEX_DUPLICATE_SOURCE:
        // Duplicate index in source: Option 1 = Drop duplicate from Source
        return `-- Execute on SOURCE database:\n-- Drop duplicate index\nDROP INDEX \`${difference.sub_object_name}\` ON ${tableName};`
      
      case DiffType.INDEX_DUPLICATE_TARGET:
        // Duplicate index in target: Option 1 = Add same duplicate to Source (not recommended)
        if (difference.target_value) {
          const idx = difference.target_value
          const unique = idx.is_unique ? 'UNIQUE ' : ''
          const columns = idx.columns || '-- columns --'
          return `-- Execute on SOURCE database:\n-- Add duplicate index (NOT RECOMMENDED)\nCREATE ${unique}INDEX \`${idx.index_name}\` ON ${tableName} (${columns});`
        }
        return `-- NOT RECOMMENDED: Duplicate index should be removed from target instead`
        
      case DiffType.CONSTRAINT_MISSING_TARGET:
        // Constraint exists only in SOURCE, missing in TARGET
        // Target → Source: DROP from SOURCE (to match Target which doesn't have it)
        if (difference.source_value) {
          const const_data = difference.source_value
          const constraintType = const_data.constraint_type
          if (constraintType === 'PRIMARY KEY') {
            return `-- Execute on SOURCE database:\nALTER TABLE ${tableName} DROP PRIMARY KEY;`
          } else if (constraintType === 'FOREIGN KEY') {
            return `-- Execute on SOURCE database:\nALTER TABLE ${tableName} DROP FOREIGN KEY ${columnName};`
          } else if (constraintType === 'UNIQUE') {
            return `-- Execute on SOURCE database:\nALTER TABLE ${tableName} DROP INDEX ${columnName};`
          }
        }
        return `-- Execute on SOURCE database:\nALTER TABLE ${tableName} DROP CONSTRAINT ${columnName};`

      case DiffType.CONSTRAINT_MISSING_SOURCE:
        // Constraint exists only in TARGET, missing in SOURCE
        // Target → Source: ADD to SOURCE (to match Target which has it)
        if (difference.target_value) {
          const const_data = difference.target_value
          const constraintType = const_data.constraint_type

          if (constraintType === 'FOREIGN KEY') {
            const columns = const_data.columns || 'column_name'
            const refTable = `\`${const_data.referenced_table_schema}\`.\`${const_data.referenced_table_name}\``
            const refColumns = const_data.referenced_columns || 'ref_column'
            const updateRule = const_data.update_rule || 'RESTRICT'
            const deleteRule = const_data.delete_rule || 'RESTRICT'
            return `-- Execute on SOURCE database:\nALTER TABLE ${tableName} ADD CONSTRAINT ${columnName} FOREIGN KEY (${columns}) REFERENCES ${refTable} (${refColumns}) ON UPDATE ${updateRule} ON DELETE ${deleteRule};`
          } else if (constraintType === 'PRIMARY KEY') {
            const columns = const_data.columns || 'column_name'
            return `-- Execute on SOURCE database:\nALTER TABLE ${tableName} ADD PRIMARY KEY (${columns});`
          } else if (constraintType === 'UNIQUE') {
            const columns = const_data.columns || 'column_name'
            return `-- Execute on SOURCE database:\nALTER TABLE ${tableName} ADD CONSTRAINT ${columnName} UNIQUE (${columns});`
          } else if (constraintType === 'CHECK') {
            const checkClause = const_data.check_clause || 'CHECK_CONDITION'
            return `-- Execute on SOURCE database:\nALTER TABLE ${tableName} ADD CONSTRAINT ${columnName} CHECK (${checkClause});`
          } else {
            const columns = const_data.columns || 'column_name'
            return `-- Execute on SOURCE database:\nALTER TABLE ${tableName} ADD CONSTRAINT ${columnName} ${constraintType} (${columns});`
          }
        }
        return `-- Unable to generate constraint definition - missing constraint data`
      
      case DiffType.CONSTRAINT_RENAMED:
        // Constraint renamed: Option 1 = Rename in Source to match Target
        if (difference.target_value) {
          const targetName = difference.target_value.constraint_name
          const constraintType = difference.target_value.constraint_type
          if (constraintType === 'UNIQUE') {
            return `-- Execute on SOURCE database:\n-- Rename UNIQUE constraint to match target\nALTER TABLE ${tableName} RENAME INDEX \`${difference.sub_object_name}\` TO \`${targetName}\`;`
          }
          return `-- Execute on SOURCE database:\n-- Rename constraint to match target\n-- Note: May require DROP and CREATE for some constraint types\nALTER TABLE ${tableName} RENAME INDEX \`${difference.sub_object_name}\` TO \`${targetName}\`;`
        }
        return `-- Execute on SOURCE database:\nALTER TABLE ${tableName} RENAME INDEX \`${difference.sub_object_name}\` TO \`new_name\`;`
        
      case DiffType.TABLE_MISSING_TARGET:
        // Source Only: Option 1 = Delete from Source
        return `-- Execute on SOURCE database:\nDROP TABLE IF EXISTS ${tableName};`

      case DiffType.TABLE_MISSING_SOURCE:
        // Target Only: Option 1 = Add to Source
        return generateCreateTableSQL(difference.target_value, tableName, 'SOURCE')

      case DiffType.PARTITION_MISSING_TARGET:
        // Partition exists in Source, missing in Target
        // Option 1: Make Source like Target = DROP partition from Source
        if (difference.sub_object_name === '(all partitions)') {
          return `-- Execute on SOURCE database:\n-- Remove partitioning from table\nALTER TABLE ${tableName} REMOVE PARTITIONING;`
        }
        return `-- Execute on SOURCE database:\n-- Drop partition to match target\nALTER TABLE ${tableName} DROP PARTITION \`${difference.sub_object_name}\`;`

      case DiffType.PARTITION_MISSING_SOURCE:
        // Partition exists in Target, missing in Source
        // Option 1: Make Source like Target = ADD partition to Source
        if (difference.sub_object_name === '(all partitions)') {
          if (difference.target_value && typeof difference.target_value === 'object') {
            const partInfo = difference.target_value
            const method = partInfo.partition_method || 'RANGE'
            const expression = partInfo.partition_expression || ''
            const partitions = partInfo.partitions || {}

            if (Object.keys(partitions).length > 0) {
              const partDefs = Object.entries(partitions)
                .sort((a: any, b: any) => (a[1].ordinal_position || 0) - (b[1].ordinal_position || 0))
                .map(([name, info]: [string, any]) => {
                  const desc = info.description || ''
                  if (method === 'LIST') {
                    return `  PARTITION \`${name}\` VALUES IN ${desc}`
                  } else {
                    return `  PARTITION \`${name}\` VALUES LESS THAN (${desc})`
                  }
                })

              return `-- Execute on SOURCE database:\n-- Add partitioning to table\nALTER TABLE ${tableName}\nPARTITION BY ${method} (${expression}) (\n${partDefs.join(',\n')}\n);`
            }
          }
          return `-- Execute on SOURCE database:\n-- Cannot generate partition SQL: missing partition info`
        }
        if (difference.target_value && typeof difference.target_value === 'object') {
          const partDesc = difference.target_value.description || 'VALUE'
          const isRange = !String(partDesc).startsWith('(')
          if (isRange) {
            return `-- Execute on SOURCE database:\n-- Add partition to match target\nALTER TABLE ${tableName} ADD PARTITION (PARTITION \`${difference.sub_object_name}\` VALUES LESS THAN (${partDesc}));`
          } else {
            return `-- Execute on SOURCE database:\n-- Add partition to match target\nALTER TABLE ${tableName} ADD PARTITION (PARTITION \`${difference.sub_object_name}\` VALUES IN ${partDesc});`
          }
        }
        return `-- Execute on SOURCE database:\nALTER TABLE ${tableName} ADD PARTITION (PARTITION \`${difference.sub_object_name}\` VALUES LESS THAN (...));`

      case DiffType.PARTITION_DEFINITION_CHANGED:
        // Partition definition changed
        // Option 1: Make Source like Target
        if (difference.sub_object_name === 'partition_method' || difference.sub_object_name === 'partition_expression') {
          return `-- Execute on SOURCE database:\n-- Changing ${difference.sub_object_name} requires table rebuild\n-- From: ${difference.source_value}\n-- To: ${difference.target_value}\n-- This requires exporting data and recreating the table`
        }
        if (difference.target_value && typeof difference.target_value === 'object') {
          const targetDesc = difference.target_value.description || 'VALUE'
          return `-- Execute on SOURCE database:\n-- Reorganize partition to match target\nALTER TABLE ${tableName} REORGANIZE PARTITION \`${difference.sub_object_name}\` INTO (\n  PARTITION \`${difference.sub_object_name}\` VALUES LESS THAN (${targetDesc})\n);`
        }
        return `-- Execute on SOURCE database:\n-- Reorganize partition\nALTER TABLE ${tableName} REORGANIZE PARTITION \`${difference.sub_object_name}\` INTO (...);`

      default:
        return `-- Forward SQL for ${difference.diff_type} will be generated in sync script`
    }
  }

  const getOption1Label = () => {
    const diffType = difference.diff_type.toLowerCase()
    if (diffType.includes('duplicate_source')) {
      return 'Drop duplicate from Source'
    }
    if (diffType.includes('duplicate_target')) {
      return 'Add duplicate to Source (NOT RECOMMENDED)'
    }
    if (diffType.includes('missing_target') || diffType.includes('removed')) {
      return 'Make Source like Target (Remove from Source)'
    }
    if (diffType.includes('missing_source') || diffType.includes('added')) {
      return 'Make Source like Target (Add to Source)'  
    }
    // For CHANGED types (type, default, nullable)
    return 'Make Source like Target (Modify Source)'
  }

  const getOption2Label = () => {
    const diffType = difference.diff_type.toLowerCase()
    if (diffType.includes('duplicate_source')) {
      return 'Keep duplicate in Source (No action)'
    }
    if (diffType.includes('duplicate_target')) {
      return 'Drop duplicate from Target (RECOMMENDED)'
    }
    if (diffType.includes('missing_target') || diffType.includes('removed')) {
      return 'Make Target like Source (Add to Target)'
    }
    if (diffType.includes('missing_source') || diffType.includes('added')) {
      return 'Make Target like Source (Remove from Target)'
    }
    // For CHANGED types (type, default, nullable)
    return 'Make Target like Source (Modify Target)'
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
            let defaultValue = ''
            if (col.column_default !== undefined && col.column_default !== null) {
              const defVal = String(col.column_default).toUpperCase()
              if (defVal === 'CURRENT_TIMESTAMP' || defVal === 'CURRENT_DATE' || defVal === 'NULL' || defVal.startsWith('CURRENT_')) {
                defaultValue = ` DEFAULT ${col.column_default}`
              } else {
                defaultValue = ` DEFAULT '${escapeSqlString(String(col.column_default))}'`
              }
            }
            const extra = col.extra ? ` ${col.extra}` : ''
            return `-- Execute on TARGET database:\nALTER TABLE ${tableName} ADD COLUMN ${columnName} ${columnType} ${nullable}${defaultValue}${extra};`
          }
        }
        return `-- Execute on TARGET database:\nALTER TABLE ${tableName} ADD COLUMN ${columnName} VARCHAR(255) NULL;`
        
      case DiffType.COLUMN_TYPE_CHANGED:
        if (difference.source_value) {
          // Source → Target: Make Target like Source (use ALL of Source's attributes)
          const sourceInfo = typeof difference.source_value === 'object' ? difference.source_value : null

          if (sourceInfo) {
            const colDef = buildColumnDefinition(sourceInfo)
            return `-- Execute on TARGET database:\nALTER TABLE ${tableName} MODIFY COLUMN ${columnName} ${colDef};`
          }

          const sourceType = typeof difference.source_value === 'string'
            ? difference.source_value
            : difference.source_value.column_type || difference.source_value.data_type
          return `-- Execute on TARGET database:\nALTER TABLE ${tableName} MODIFY COLUMN ${columnName} ${sourceType};`
        }
        return `-- Unable to determine source column type`
        
      case DiffType.COLUMN_NULLABLE_CHANGED:
        if (difference.source_value !== undefined) {
          // Source → Target: Make Target like Source (use ALL of Source's attributes)
          const sourceInfo = typeof difference.source_value === 'object' ? difference.source_value : null

          if (sourceInfo) {
            const colDef = buildColumnDefinition(sourceInfo)
            return `-- Execute on TARGET database:\nALTER TABLE ${tableName} MODIFY COLUMN ${columnName} ${colDef};`
          }

          const sourceNullable = typeof difference.source_value === 'object'
            ? difference.source_value.is_nullable
            : difference.source_value
          const columnType = typeof difference.source_value === 'object'
            ? difference.source_value.column_type
            : 'VARCHAR(255)'
          const nullable = sourceNullable ? 'NULL' : 'NOT NULL'

          return `-- Execute on TARGET database:\nALTER TABLE ${tableName} MODIFY COLUMN ${columnName} ${columnType} ${nullable};`
        }
        return `-- Unable to determine source column info`
        
      case DiffType.COLUMN_DEFAULT_CHANGED:
        if (difference.source_value !== undefined) {
          // Source → Target: Make Target like Source (use Source's attributes)
          const sourceInfo = typeof difference.source_value === 'object' ? difference.source_value : null

          if (sourceInfo) {
            // Use full column definition with MODIFY COLUMN
            const colDef = buildColumnDefinition(sourceInfo)
            return `-- Execute on TARGET database:\nALTER TABLE ${tableName} MODIFY COLUMN ${columnName} ${colDef};`
          }

          // Fallback for primitive value
          if (difference.source_value === null) {
            return `-- Execute on TARGET database:\nALTER TABLE ${tableName} ALTER COLUMN ${columnName} DROP DEFAULT;`
          } else {
            const defaultVal = String(difference.source_value)
            const quotedDefault = defaultVal.toUpperCase().startsWith('CURRENT_') || defaultVal.toUpperCase() === 'NULL'
              ? defaultVal
              : `'${defaultVal}'`
            return `-- Execute on TARGET database:\nALTER TABLE ${tableName} ALTER COLUMN ${columnName} SET DEFAULT ${quotedDefault};`
          }
        }
        return `-- Unable to determine source default value`
      
      case DiffType.COLUMN_EXTRA_CHANGED:
        // Handle comment, charset, collation changes
        if (difference.source_value && typeof difference.source_value === 'object') {
          const sourceInfo = difference.source_value
          const colDef = buildColumnDefinition(sourceInfo)
          return `-- Execute on TARGET database:\nALTER TABLE ${tableName} MODIFY COLUMN ${columnName} ${colDef};`
        }
        return `-- Execute on TARGET database:\n-- Modify column extra properties\nALTER TABLE ${tableName} MODIFY COLUMN ${columnName} /* update properties */;`

      case DiffType.COLUMN_RENAMED:
        // Column renamed: Option 2 = Rename in Target to match Source
        // source_display_value = source name (desired), target_display_value = target name (current)
        if (difference.source_value && typeof difference.source_value === 'object') {
          const targetName = difference.target_display_value || 'target_name'
          const sourceName = difference.source_display_value || difference.sub_object_name
          const colDef = buildColumnDefinition(difference.source_value)
          return `-- Execute on TARGET database:\n-- Rename column to match source\nALTER TABLE ${tableName} CHANGE COLUMN \`${targetName}\` \`${sourceName}\` ${colDef};`
        }
        return `-- Execute on TARGET database:\nALTER TABLE ${tableName} CHANGE COLUMN \`old_name\` ${columnName} /* column definition */;`

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
      
      case DiffType.INDEX_RENAMED:
        // Index renamed: Option 2 = Rename in Target to match Source
        if (difference.target_value) {
          const targetName = difference.target_value.index_name
          return `-- Execute on TARGET database:\n-- Rename index to match source\nALTER TABLE ${tableName} RENAME INDEX \`${targetName}\` TO \`${difference.sub_object_name}\`;`
        }
        return `-- Execute on TARGET database:\nALTER TABLE ${tableName} RENAME INDEX \`old_name\` TO \`${difference.sub_object_name}\`;`
      
      case DiffType.INDEX_DUPLICATE_SOURCE:
        // Duplicate index in source: Option 2 = Keep duplicate (no action needed on target)
        return `-- No action needed on TARGET\n-- Duplicate index exists only in SOURCE`
      
      case DiffType.INDEX_DUPLICATE_TARGET:
        // Duplicate index in target: Option 2 = Drop duplicate from Target (RECOMMENDED)
        if (difference.target_value) {
          return `-- Execute on TARGET database:\n-- Drop duplicate index (RECOMMENDED)\nDROP INDEX \`${difference.target_value.index_name}\` ON ${tableName};`
        }
        return `-- Execute on TARGET database:\n-- Drop duplicate index\nDROP INDEX \`${difference.sub_object_name}\` ON ${tableName};`
        
      case DiffType.CONSTRAINT_MISSING_TARGET:
        // Constraint exists only in SOURCE, missing in TARGET
        // Source → Target: ADD to TARGET (to match Source which has it)
        if (difference.source_value) {
          const const_data = difference.source_value
          const constraintType = const_data.constraint_type

          if (constraintType === 'FOREIGN KEY') {
            const columns = const_data.columns || 'column_name'
            const refTable = `\`${const_data.referenced_table_schema}\`.\`${const_data.referenced_table_name}\``
            const refColumns = const_data.referenced_columns || 'ref_column'
            const updateRule = const_data.update_rule || 'RESTRICT'
            const deleteRule = const_data.delete_rule || 'RESTRICT'
            return `-- Execute on TARGET database:\nALTER TABLE ${tableName} ADD CONSTRAINT ${columnName} FOREIGN KEY (${columns}) REFERENCES ${refTable} (${refColumns}) ON UPDATE ${updateRule} ON DELETE ${deleteRule};`
          } else if (constraintType === 'PRIMARY KEY') {
            const columns = const_data.columns || 'column_name'
            return `-- Execute on TARGET database:\nALTER TABLE ${tableName} ADD PRIMARY KEY (${columns});`
          } else if (constraintType === 'UNIQUE') {
            const columns = const_data.columns || 'column_name'
            return `-- Execute on TARGET database:\nALTER TABLE ${tableName} ADD CONSTRAINT ${columnName} UNIQUE (${columns});`
          } else if (constraintType === 'CHECK') {
            const checkClause = const_data.check_clause || 'CHECK_CONDITION'
            return `-- Execute on TARGET database:\nALTER TABLE ${tableName} ADD CONSTRAINT ${columnName} CHECK (${checkClause});`
          } else {
            const columns = const_data.columns || 'column_name'
            return `-- Execute on TARGET database:\nALTER TABLE ${tableName} ADD CONSTRAINT ${columnName} ${constraintType} (${columns});`
          }
        }
        return `-- Unable to generate constraint definition - missing constraint data`

      case DiffType.CONSTRAINT_MISSING_SOURCE:
        // Constraint exists only in TARGET, missing in SOURCE
        // Source → Target: DROP from TARGET (to match Source which doesn't have it)
        if (difference.target_value) {
          const const_data = difference.target_value
          const constraintType = const_data.constraint_type
          if (constraintType === 'PRIMARY KEY') {
            return `-- Execute on TARGET database:\nALTER TABLE ${tableName} DROP PRIMARY KEY;`
          } else if (constraintType === 'FOREIGN KEY') {
            return `-- Execute on TARGET database:\nALTER TABLE ${tableName} DROP FOREIGN KEY ${columnName};`
          } else if (constraintType === 'UNIQUE') {
            return `-- Execute on TARGET database:\nALTER TABLE ${tableName} DROP INDEX ${columnName};`
          }
        }
        return `-- Execute on TARGET database:\nALTER TABLE ${tableName} DROP CONSTRAINT ${columnName};`
      
      case DiffType.CONSTRAINT_RENAMED:
        // Constraint renamed: Option 2 = Rename in Target to match Source
        if (difference.target_value) {
          const targetName = difference.target_value.constraint_name
          const constraintType = difference.target_value.constraint_type
          if (constraintType === 'UNIQUE') {
            return `-- Execute on TARGET database:\n-- Rename UNIQUE constraint to match source\nALTER TABLE ${tableName} RENAME INDEX \`${targetName}\` TO \`${difference.sub_object_name}\`;`
          }
          return `-- Execute on TARGET database:\n-- Rename constraint to match source\n-- Note: May require DROP and CREATE for some constraint types\nALTER TABLE ${tableName} RENAME INDEX \`${targetName}\` TO \`${difference.sub_object_name}\`;`
        }
        return `-- Execute on TARGET database:\nALTER TABLE ${tableName} RENAME INDEX \`old_name\` TO \`${difference.sub_object_name}\`;`
        
      case DiffType.TABLE_MISSING_TARGET:
        // Source Only: Option 2 = Add to Target
        return generateCreateTableSQL(difference.source_value, tableName, 'TARGET')

      case DiffType.TABLE_MISSING_SOURCE:
        // Target Only: Option 2 = Delete from Target
        return `-- Execute on TARGET database:\nDROP TABLE IF EXISTS ${tableName};`

      case DiffType.PARTITION_MISSING_TARGET:
        // Partition exists in Source, missing in Target
        // Option 2: Make Target like Source = ADD partition to Target
        if (difference.sub_object_name === '(all partitions)') {
          if (difference.source_value && typeof difference.source_value === 'object') {
            const partInfo = difference.source_value
            const method = partInfo.partition_method || 'RANGE'
            const expression = partInfo.partition_expression || ''
            const partitions = partInfo.partitions || {}

            if (Object.keys(partitions).length > 0) {
              const partDefs = Object.entries(partitions)
                .sort((a: any, b: any) => (a[1].ordinal_position || 0) - (b[1].ordinal_position || 0))
                .map(([name, info]: [string, any]) => {
                  const desc = info.description || ''
                  if (method === 'LIST') {
                    return `  PARTITION \`${name}\` VALUES IN ${desc}`
                  } else {
                    return `  PARTITION \`${name}\` VALUES LESS THAN (${desc})`
                  }
                })

              return `-- Execute on TARGET database:\n-- Add partitioning to table\nALTER TABLE ${tableName}\nPARTITION BY ${method} (${expression}) (\n${partDefs.join(',\n')}\n);`
            }
          }
          return `-- Execute on TARGET database:\n-- Cannot generate partition SQL: missing partition info`
        }
        if (difference.source_value && typeof difference.source_value === 'object') {
          const partDesc = difference.source_value.description || 'VALUE'
          const isRange = !String(partDesc).startsWith('(')
          if (isRange) {
            return `-- Execute on TARGET database:\n-- Add partition to match source\nALTER TABLE ${tableName} ADD PARTITION (PARTITION \`${difference.sub_object_name}\` VALUES LESS THAN (${partDesc}));`
          } else {
            return `-- Execute on TARGET database:\n-- Add partition to match source\nALTER TABLE ${tableName} ADD PARTITION (PARTITION \`${difference.sub_object_name}\` VALUES IN ${partDesc});`
          }
        }
        return `-- Execute on TARGET database:\nALTER TABLE ${tableName} ADD PARTITION (PARTITION \`${difference.sub_object_name}\` VALUES LESS THAN (...));`

      case DiffType.PARTITION_MISSING_SOURCE:
        // Partition exists in Target, missing in Source
        // Option 2: Make Target like Source = DROP partition from Target
        if (difference.sub_object_name === '(all partitions)') {
          return `-- Execute on TARGET database:\n-- Remove partitioning from table\nALTER TABLE ${tableName} REMOVE PARTITIONING;`
        }
        return `-- Execute on TARGET database:\n-- Drop partition to match source\n-- WARNING: This will DELETE all data in the partition!\nALTER TABLE ${tableName} DROP PARTITION \`${difference.sub_object_name}\`;`

      case DiffType.PARTITION_DEFINITION_CHANGED:
        // Partition definition changed
        // Option 2: Make Target like Source
        if (difference.sub_object_name === 'partition_method' || difference.sub_object_name === 'partition_expression') {
          return `-- Execute on TARGET database:\n-- Changing ${difference.sub_object_name} requires table rebuild\n-- From: ${difference.target_value}\n-- To: ${difference.source_value}\n-- This requires exporting data and recreating the table`
        }
        if (difference.source_value && typeof difference.source_value === 'object') {
          const sourceDesc = difference.source_value.description || 'VALUE'
          return `-- Execute on TARGET database:\n-- Reorganize partition to match source\nALTER TABLE ${tableName} REORGANIZE PARTITION \`${difference.sub_object_name}\` INTO (\n  PARTITION \`${difference.sub_object_name}\` VALUES LESS THAN (${sourceDesc})\n);`
        }
        return `-- Execute on TARGET database:\n-- Reorganize partition\nALTER TABLE ${tableName} REORGANIZE PARTITION \`${difference.sub_object_name}\` INTO (...);`

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

      {/* Values Comparison - Always show both Source and Target for clarity */}
      {(difference.source_value !== undefined || difference.target_value !== undefined) && (
        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            {/* Source Value */}
            <div className="rounded-lg border-2 border-blue-300 dark:border-blue-700 p-3">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Database className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                  <span className="text-sm font-medium">Source</span>
                </div>
                {getSourceLabel() && (
                  <span className="text-xs text-muted-foreground">{getSourceLabel()}</span>
                )}
              </div>
              {difference.source_value !== undefined && difference.source_value !== null ? (
                formatValue(difference.source_value, difference.object_type)
              ) : (
                <p className="text-sm text-muted-foreground italic">
                  {getDiffTypeLabel() === 'Target Only' ? '(Does not exist)' : '(NULL)'}
                </p>
              )}
            </div>

            {/* Target Value */}
            <div className="rounded-lg border-2 border-green-300 dark:border-green-700 p-3">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Database className="h-4 w-4 text-green-600 dark:text-green-400" />
                  <span className="text-sm font-medium">Target</span>
                </div>
                {getTargetLabel() && (
                  <span className="text-xs text-muted-foreground">{getTargetLabel()}</span>
                )}
              </div>
              {difference.target_value !== undefined && difference.target_value !== null ? (
                formatValue(difference.target_value, difference.object_type)
              ) : (
                <p className="text-sm text-muted-foreground italic">
                  {getDiffTypeLabel() === 'Source Only' ? '(Does not exist)' : '(NULL)'}
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* SQL Preview - Two options for syncing */}
      <div className="space-y-3">
        <p className="text-sm text-muted-foreground">Choose how to resolve this difference:</p>
        
        {/* Option 1: Target → Source direction */}
        <div className="rounded-lg border bg-card p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Code className="h-4 w-4 text-green-600" />
              <span className="text-sm font-medium">
                Target → Source
                <span className="ml-2 text-xs font-normal text-muted-foreground">
                  {getOption1Label()}
                </span>
              </span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => copyToClipboard(generateOption1SQL())}
            >
              <Copy className="h-3 w-3" />
            </Button>
          </div>
          <SyntaxHighlighter 
            language="sql" 
            style={oneDark}
            customStyle={{
              margin: 0,
              borderRadius: '0.375rem',
              fontSize: '0.75rem',
            }}
          >
            {generateOption1SQL()}
          </SyntaxHighlighter>
        </div>

        {/* Option 2: Source → Target direction */}
        <div className="rounded-lg border bg-card p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Code className="h-4 w-4 text-blue-600" />
              <span className="text-sm font-medium">
                Source → Target
                <span className="ml-2 text-xs font-normal text-muted-foreground">
                  {getOption2Label()}
                </span>
              </span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => copyToClipboard(generateOption2SQL())}
            >
              <Copy className="h-3 w-3" />
            </Button>
          </div>
          <SyntaxHighlighter 
            language="sql" 
            style={oneDark}
            customStyle={{
              margin: 0,
              borderRadius: '0.375rem',
              fontSize: '0.75rem',
            }}
          >
            {generateOption2SQL()}
          </SyntaxHighlighter>
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
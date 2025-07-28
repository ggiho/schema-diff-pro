'use client'

import { useState } from 'react'
import { Difference, SeverityLevel, ObjectType } from '@/types'
import { AlertCircle, AlertTriangle, ChevronDown, ChevronRight, Filter, Info, XCircle } from 'lucide-react'
import { Button } from './ui/button'
import { DifferenceDetail } from './DifferenceDetail'

interface DifferencesListProps {
  differences: Difference[]
}

export function DifferencesList({ differences }: DifferencesListProps) {
  const [expandedItems, setExpandedItems] = useState<Set<number>>(new Set())
  const [filters, setFilters] = useState({
    severity: '',
    objectType: '',
    source: '',
    search: '',
  })

  const toggleExpanded = (index: number) => {
    const newExpanded = new Set(expandedItems)
    if (newExpanded.has(index)) {
      newExpanded.delete(index)
    } else {
      newExpanded.add(index)
    }
    setExpandedItems(newExpanded)
  }

  const severityConfig = {
    [SeverityLevel.CRITICAL]: { icon: XCircle, color: 'text-red-500' },
    [SeverityLevel.HIGH]: { icon: AlertCircle, color: 'text-orange-500' },
    [SeverityLevel.MEDIUM]: { icon: AlertTriangle, color: 'text-yellow-500' },
    [SeverityLevel.LOW]: { icon: Info, color: 'text-blue-500' },
    [SeverityLevel.INFO]: { icon: Info, color: 'text-gray-500' },
  }

  const getSourceType = (diff: Difference) => {
    const diffType = diff.diff_type.toLowerCase()
    if (diffType.includes('missing_target') || diffType.includes('removed')) {
      return 'source-only' // 소스에만 있음
    }
    if (diffType.includes('missing_source') || diffType.includes('added')) {
      return 'target-only' // 타겟에만 있음
    }
    return 'both' // 둘 다 있지만 다름
  }

  const filteredDifferences = differences.filter((diff) => {
    if (filters.severity && diff.severity !== filters.severity) return false
    if (filters.objectType && diff.object_type !== filters.objectType) return false
    if (filters.source && getSourceType(diff) !== filters.source) return false
    if (filters.search) {
      const searchLower = filters.search.toLowerCase()
      return (
        diff.object_name.toLowerCase().includes(searchLower) ||
        diff.description.toLowerCase().includes(searchLower) ||
        (diff.schema_name?.toLowerCase().includes(searchLower) ?? false)
      )
    }
    return true
  })

  const uniqueSeverities = Array.from(new Set(differences.map(d => d.severity)))
    .sort((a, b) => {
      const severityOrder = ['critical', 'high', 'medium', 'low', 'info']
      return severityOrder.indexOf(a.toLowerCase()) - severityOrder.indexOf(b.toLowerCase())
    })
  const uniqueObjectTypes = Array.from(new Set(differences.map(d => d.object_type)))

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-4 rounded-lg border bg-card p-4">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">Filters:</span>
        </div>
        
        <select
          value={filters.severity}
          onChange={(e) => setFilters({ ...filters, severity: e.target.value })}
          className="rounded border bg-background px-3 py-1 text-sm"
        >
          <option value="">All Severities</option>
          {uniqueSeverities.map((severity) => (
            <option key={severity} value={severity}>
              {severity.charAt(0).toUpperCase() + severity.slice(1)}
            </option>
          ))}
        </select>

        <select
          value={filters.objectType}
          onChange={(e) => setFilters({ ...filters, objectType: e.target.value })}
          className="rounded border bg-background px-3 py-1 text-sm"
        >
          <option value="">All Object Types</option>
          {uniqueObjectTypes.map((type) => (
            <option key={type} value={type}>
              {type.charAt(0).toUpperCase() + type.slice(1)}
            </option>
          ))}
        </select>

        <select
          value={filters.source}
          onChange={(e) => setFilters({ ...filters, source: e.target.value })}
          className="rounded border bg-background px-3 py-1 text-sm"
        >
          <option value="">All Sources</option>
          <option value="source-only">Source Only</option>
          <option value="target-only">Target Only</option>
          <option value="both">Different</option>
        </select>

        <input
          type="text"
          placeholder="Search..."
          value={filters.search}
          onChange={(e) => setFilters({ ...filters, search: e.target.value })}
          className="rounded border bg-background px-3 py-1 text-sm"
        />

        <Button
          variant="ghost"
          size="sm"
          onClick={() => setFilters({ severity: '', objectType: '', source: '', search: '' })}
        >
          Clear
        </Button>
      </div>

      {/* Results count */}
      <p className="text-sm text-muted-foreground">
        Showing {filteredDifferences.length} of {differences.length} differences
      </p>

      {/* Differences list */}
      <div className="space-y-2">
        {filteredDifferences.map((diff, index) => {
          const isExpanded = expandedItems.has(index)
          const SeverityIcon = severityConfig[diff.severity].icon
          const severityColor = severityConfig[diff.severity].color

          return (
            <div key={index} className="rounded-lg border bg-card">
              <button
                onClick={() => toggleExpanded(index)}
                className="flex w-full items-start gap-3 p-4 text-left hover:bg-accent/50"
              >
                <div className="mt-0.5">
                  {isExpanded ? (
                    <ChevronDown className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                </div>
                
                <SeverityIcon className={`h-5 w-5 ${severityColor}`} />
                
                <div className="flex-1">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="font-medium">
                        {diff.schema_name && `${diff.schema_name}.`}
                        {diff.object_name}
                        {diff.sub_object_name && `.${diff.sub_object_name}`}
                      </p>
                      <p className="text-sm text-muted-foreground">{diff.description}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="rounded bg-secondary px-2 py-1 text-xs">
                        {diff.object_type}
                      </span>
                      {/* Source type indicator */}
                      {(() => {
                        const sourceType = getSourceType(diff)
                        if (sourceType === 'source-only') {
                          return (
                            <span className="rounded bg-blue-100 px-2 py-1 text-xs text-blue-700">
                              Source Only
                            </span>
                          )
                        }
                        if (sourceType === 'target-only') {
                          return (
                            <span className="rounded bg-red-100 px-2 py-1 text-xs text-red-700">
                              Target Only
                            </span>
                          )
                        }
                        return (
                          <span className="rounded bg-orange-100 px-2 py-1 text-xs text-orange-700">
                            Different
                          </span>
                        )
                      })()}
                      {diff.can_auto_fix && (
                        <span className="rounded bg-green-100 px-2 py-1 text-xs text-green-700">
                          Auto-fixable
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </button>

              {isExpanded && (
                <div className="border-t px-4 py-3">
                  <DifferenceDetail difference={diff} />
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
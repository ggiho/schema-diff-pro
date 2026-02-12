'use client'

import { useState } from 'react'
import { Difference, SeverityLevel, ObjectType } from '@/types'
import { AlertCircle, AlertTriangle, ChevronDown, ChevronRight, Filter, Info, XCircle } from 'lucide-react'
import { Button } from './ui/button'
import { DifferenceDetail } from './DifferenceDetail'

interface DifferencesListProps {
  differences: Difference[]
  onFiltersChange?: (filters: { schema: string; objectType: string; severity: string }) => void
  initialFilters?: { schema: string; objectType: string; severity: string }
}

export function DifferencesList({ differences, onFiltersChange, initialFilters }: DifferencesListProps) {
  const [expandedItems, setExpandedItems] = useState<Set<number>>(new Set())
  const [filters, setFilters] = useState({
    severity: initialFilters?.severity || '',
    objectType: initialFilters?.objectType || '',
    schema: initialFilters?.schema || '',
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
    if (filters.schema && diff.schema_name !== filters.schema) return false
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
  const uniqueSchemas = Array.from(new Set(differences.map(d => d.schema_name).filter(Boolean)))

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="rounded-lg border border-border/40 bg-card/30 backdrop-blur-sm">
        <div className="flex flex-wrap items-center gap-3 p-4">
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-muted-foreground/70" />
            <span className="text-sm font-medium text-foreground/80">Filter by</span>
            {(filters.severity || filters.objectType || filters.schema || filters.source) && (
              <div className="flex items-center gap-1.5 ml-1">
                <div className="h-1.5 w-1.5 rounded-full bg-foreground/60 animate-pulse" />
                <span className="text-xs font-medium text-foreground/60">
                  {[filters.severity, filters.objectType, filters.schema, filters.source].filter(Boolean).length}
                </span>
              </div>
            )}
          </div>

          <select
            value={filters.severity}
            onChange={(e) => {
              const newFilters = { ...filters, severity: e.target.value }
              setFilters(newFilters)
              onFiltersChange?.({ schema: newFilters.schema, objectType: newFilters.objectType, severity: newFilters.severity })
            }}
            className="h-8 rounded-md border border-border/50 bg-background/80 px-3 text-sm text-foreground/90 shadow-sm transition-colors hover:border-border focus:border-foreground/30 focus:outline-none focus:ring-1 focus:ring-foreground/20"
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
            onChange={(e) => {
              const newFilters = { ...filters, objectType: e.target.value }
              setFilters(newFilters)
              onFiltersChange?.({ schema: newFilters.schema, objectType: newFilters.objectType, severity: newFilters.severity })
            }}
            className="h-8 rounded-md border border-border/50 bg-background/80 px-3 text-sm text-foreground/90 shadow-sm transition-colors hover:border-border focus:border-foreground/30 focus:outline-none focus:ring-1 focus:ring-foreground/20"
          >
            <option value="">All Object Types</option>
            {uniqueObjectTypes.map((type) => (
              <option key={type} value={type}>
                {type.charAt(0).toUpperCase() + type.slice(1)}
              </option>
            ))}
          </select>

          <select
            value={filters.schema}
            onChange={(e) => {
              const newFilters = { ...filters, schema: e.target.value }
              setFilters(newFilters)
              onFiltersChange?.({ schema: newFilters.schema, objectType: newFilters.objectType, severity: newFilters.severity })
            }}
            className="h-8 rounded-md border border-border/50 bg-background/80 px-3 text-sm text-foreground/90 shadow-sm transition-colors hover:border-border focus:border-foreground/30 focus:outline-none focus:ring-1 focus:ring-foreground/20"
          >
            <option value="">All Schemas</option>
            {uniqueSchemas.map((schema) => (
              <option key={schema} value={schema}>
                {schema}
              </option>
            ))}
          </select>

          <select
            value={filters.source}
            onChange={(e) => setFilters({ ...filters, source: e.target.value })}
            className="h-8 rounded-md border border-border/50 bg-background/80 px-3 text-sm text-foreground/90 shadow-sm transition-colors hover:border-border focus:border-foreground/30 focus:outline-none focus:ring-1 focus:ring-foreground/20"
          >
            <option value="">All Sources</option>
            <option value="source-only">Source Only</option>
            <option value="target-only">Target Only</option>
            <option value="both">Different</option>
          </select>

          <input
            type="text"
            placeholder="Search differences..."
            value={filters.search}
            onChange={(e) => setFilters({ ...filters, search: e.target.value })}
            className="h-8 min-w-[180px] rounded-md border border-border/50 bg-background/80 px-3 text-sm text-foreground/90 placeholder:text-muted-foreground/50 shadow-sm transition-colors hover:border-border focus:border-foreground/30 focus:outline-none focus:ring-1 focus:ring-foreground/20"
          />

          {(filters.severity || filters.objectType || filters.schema || filters.source) && (
            <>
              <div className="h-4 w-px bg-border/40" />
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setFilters({ severity: '', objectType: '', schema: '', source: '', search: '' })
                  onFiltersChange?.({ schema: '', objectType: '', severity: '' })
                }}
                className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
              >
                Clear all
              </Button>
            </>
          )}
        </div>

        {/* Active filter tags */}
        {(filters.schema || filters.objectType || filters.severity) && (
          <div className="flex flex-wrap items-center gap-2 border-t border-border/30 bg-muted/20 px-4 py-2.5">
            <span className="text-xs text-muted-foreground/70">Active:</span>
            {filters.schema && (
              <button
                onClick={() => {
                  const newFilters = { ...filters, schema: '' }
                  setFilters(newFilters)
                  onFiltersChange?.({ schema: '', objectType: newFilters.objectType, severity: newFilters.severity })
                }}
                className="group inline-flex items-center gap-1.5 rounded-md border border-border/40 bg-background/60 px-2.5 py-1 text-xs font-medium text-foreground/80 shadow-sm transition-all hover:border-border hover:bg-background hover:shadow"
              >
                <span className="text-muted-foreground/60">Schema:</span>
                <span>{filters.schema}</span>
                <span className="ml-0.5 text-muted-foreground/40 transition-colors group-hover:text-foreground/60">×</span>
              </button>
            )}
            {filters.objectType && (
              <button
                onClick={() => {
                  const newFilters = { ...filters, objectType: '' }
                  setFilters(newFilters)
                  onFiltersChange?.({ schema: newFilters.schema, objectType: '', severity: newFilters.severity })
                }}
                className="group inline-flex items-center gap-1.5 rounded-md border border-border/40 bg-background/60 px-2.5 py-1 text-xs font-medium text-foreground/80 shadow-sm transition-all hover:border-border hover:bg-background hover:shadow"
              >
                <span className="text-muted-foreground/60">Type:</span>
                <span>{filters.objectType}</span>
                <span className="ml-0.5 text-muted-foreground/40 transition-colors group-hover:text-foreground/60">×</span>
              </button>
            )}
            {filters.severity && (
              <button
                onClick={() => {
                  const newFilters = { ...filters, severity: '' }
                  setFilters(newFilters)
                  onFiltersChange?.({ schema: newFilters.schema, objectType: newFilters.objectType, severity: '' })
                }}
                className="group inline-flex items-center gap-1.5 rounded-md border border-border/40 bg-background/60 px-2.5 py-1 text-xs font-medium text-foreground/80 shadow-sm transition-all hover:border-border hover:bg-background hover:shadow"
              >
                <span className="text-muted-foreground/60">Severity:</span>
                <span>{filters.severity}</span>
                <span className="ml-0.5 text-muted-foreground/40 transition-colors group-hover:text-foreground/60">×</span>
              </button>
            )}
          </div>
        )}
      </div>

      {/* Results count */}
      <div className={
        filteredDifferences.length < differences.length
          ? "flex items-center gap-2 rounded-md border border-border/40 bg-muted/30 px-3.5 py-2 text-sm font-medium text-foreground/80 backdrop-blur-sm"
          : "text-sm text-muted-foreground/70"
      }>
        {filteredDifferences.length < differences.length ? (
          <>
            <div className="h-1.5 w-1.5 rounded-full bg-foreground/40" />
            <span>
              Showing <span className="font-semibold text-foreground">{filteredDifferences.length}</span>
              <span className="text-muted-foreground/60"> of </span>
              <span className="font-semibold text-foreground">{differences.length}</span>
              <span className="text-muted-foreground/60"> results</span>
            </span>
          </>
        ) : (
          <span>Showing <span className="font-medium text-foreground/70">{filteredDifferences.length}</span> results</span>
        )}
      </div>

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
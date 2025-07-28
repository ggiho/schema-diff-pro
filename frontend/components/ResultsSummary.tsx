'use client'

import { ComparisonResult, SeverityLevel } from '@/types'
import { AlertCircle, AlertTriangle, CheckCircle, Info, XCircle } from 'lucide-react'

interface ResultsSummaryProps {
  result: ComparisonResult
}

export function ResultsSummary({ result }: ResultsSummaryProps) {
  const severityConfig = {
    [SeverityLevel.CRITICAL]: {
      icon: XCircle,
      color: 'text-red-500',
      bgColor: 'bg-red-50',
      label: 'Critical',
    },
    [SeverityLevel.HIGH]: {
      icon: AlertCircle,
      color: 'text-orange-500',
      bgColor: 'bg-orange-50',
      label: 'High',
    },
    [SeverityLevel.MEDIUM]: {
      icon: AlertTriangle,
      color: 'text-yellow-500',
      bgColor: 'bg-yellow-50',
      label: 'Medium',
    },
    [SeverityLevel.LOW]: {
      icon: Info,
      color: 'text-blue-500',
      bgColor: 'bg-blue-50',
      label: 'Low',
    },
    [SeverityLevel.INFO]: {
      icon: Info,
      color: 'text-gray-500',
      bgColor: 'bg-gray-50',
      label: 'Info',
    },
  }

  const duration = result.duration_seconds
    ? `${Math.round(result.duration_seconds)}s`
    : 'N/A'

  return (
    <div className="space-y-6">
      {/* Overview Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <div className="rounded-lg border bg-card p-4">
          <p className="text-sm text-muted-foreground">Total Differences</p>
          <p className="text-2xl font-bold">{result.summary.total_differences}</p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-sm text-muted-foreground">Objects Compared</p>
          <p className="text-2xl font-bold">{result.objects_compared}</p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-sm text-muted-foreground">Duration</p>
          <p className="text-2xl font-bold">{duration}</p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-sm text-muted-foreground">Auto-Fixable</p>
          <p className="text-2xl font-bold">{result.summary.can_auto_fix}</p>
        </div>
      </div>

      {/* Severity Breakdown */}
      <div className="rounded-lg border bg-card p-6">
        <h3 className="mb-4 text-lg font-semibold">Differences by Severity</h3>
        <div className="space-y-3">
          {Object.entries(severityConfig).map(([severity, config]) => {
            const count = result.summary.by_severity[severity] || 0
            const Icon = config.icon
            
            return (
              <div key={severity} className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`rounded-full p-2 ${config.bgColor}`}>
                    <Icon className={`h-4 w-4 ${config.color}`} />
                  </div>
                  <span className="font-medium">{config.label}</span>
                </div>
                <span className="text-2xl font-bold">{count}</span>
              </div>
            )
          })}
        </div>
      </div>

      {/* Affected Objects */}
      <div className="grid gap-6 md:grid-cols-2">
        <div className="rounded-lg border bg-card p-6">
          <h3 className="mb-4 text-lg font-semibold">
            Affected Schemas ({result.summary.schemas_affected.length})
          </h3>
          {result.summary.schemas_affected.length > 0 ? (
            <div className="space-y-2">
              {result.summary.schemas_affected.map((schema) => (
                <div key={schema} className="rounded-md bg-white px-3 py-2 border">
                  <span className="text-sm font-medium">{schema}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No schemas affected</p>
          )}
        </div>

        <div className="rounded-lg border bg-card p-6">
          <h3 className="mb-4 text-lg font-semibold">Object Types</h3>
          <div className="space-y-2">
            {Object.entries(result.summary.by_object_type).map(([type, count]) => (
              <div key={type} className="flex items-center justify-between">
                <span className="text-sm capitalize">{type}</span>
                <span className="font-medium">{count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Warnings */}
      {result.summary.data_loss_risks.length > 0 && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-6">
          <div className="mb-3 flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-destructive" />
            <h3 className="text-lg font-semibold">Data Loss Risks</h3>
          </div>
          <ul className="space-y-2">
            {result.summary.data_loss_risks.map((risk, index) => (
              <li key={index} className="text-sm">
                • {risk.object}: {risk.description}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
'use client'

import { ComparisonOptions as ComparisonOptionsType } from '@/types'
import { Settings } from 'lucide-react'

interface ComparisonOptionsProps {
  options: ComparisonOptionsType
  onChange: (options: ComparisonOptionsType) => void
}

export function ComparisonOptions({ options, onChange }: ComparisonOptionsProps) {
  const handleToggle = (field: keyof ComparisonOptionsType) => {
    onChange({ ...options, [field]: !options[field] })
  }

  return (
    <div className="rounded-lg border bg-card p-6">
      <div className="mb-4 flex items-center gap-2">
        <Settings className="h-5 w-5 text-primary" />
        <h2 className="text-lg font-semibold">Comparison Options</h2>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div>
          <h3 className="mb-3 text-sm font-medium">Compare Objects</h3>
          <div className="space-y-2">
            {[
              { key: 'compare_tables', label: 'Tables & Columns' },
              { key: 'compare_indexes', label: 'Indexes' },
              { key: 'compare_constraints', label: 'Constraints (PK, FK, Unique)' },
              { key: 'compare_partitions', label: 'Partitions (can be slow)', warning: true },
              { key: 'compare_procedures', label: 'Stored Procedures' },
              { key: 'compare_functions', label: 'Functions' },
              { key: 'compare_views', label: 'Views' },
              { key: 'compare_triggers', label: 'Triggers' },
              { key: 'compare_events', label: 'Events' },
            ].map(({ key, label, warning }) => (
              <label key={key} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={options[key as keyof ComparisonOptionsType] as boolean}
                  onChange={() => handleToggle(key as keyof ComparisonOptionsType)}
                  className="rounded border-gray-300"
                />
                <span className={`text-sm ${warning ? 'text-amber-600' : ''}`}>{label}</span>
              </label>
            ))}
          </div>
        </div>

        <div>
          <h3 className="mb-3 text-sm font-medium">Comparison Settings</h3>
          <div className="space-y-2">
            {[
              { key: 'ignore_auto_increment', label: 'Ignore AUTO_INCREMENT values' },
              { key: 'ignore_comments', label: 'Ignore comments' },
              { key: 'ignore_charset', label: 'Ignore character sets' },
              { key: 'ignore_collation', label: 'Ignore collations' },
              { key: 'case_sensitive', label: 'Case sensitive comparison' },
            ].map(({ key, label }) => (
              <label key={key} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={options[key as keyof ComparisonOptionsType] as boolean}
                  onChange={() => handleToggle(key as keyof ComparisonOptionsType)}
                  className="rounded border-gray-300"
                />
                <span className="text-sm">{label}</span>
              </label>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
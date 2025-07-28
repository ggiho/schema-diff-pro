'use client'

import { useState, useEffect } from 'react'
import { Clock, Database } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

interface RecentComparison {
  id: string
  source: string
  target: string
  timestamp: Date
  differenceCount: number
}

export function RecentComparisons() {
  const [recentComparisons, setRecentComparisons] = useState<RecentComparison[]>([])

  useEffect(() => {
    // In a real app, this would fetch from localStorage or API
    const mockData: RecentComparison[] = [
      {
        id: '1',
        source: 'dev.mysql.com',
        target: 'prod.mysql.com',
        timestamp: new Date(Date.now() - 3600000), // 1 hour ago
        differenceCount: 47,
      },
      {
        id: '2',
        source: 'dev.mysql.com',
        target: 'staging.mysql.com',
        timestamp: new Date(Date.now() - 86400000), // 1 day ago
        differenceCount: 12,
      },
      {
        id: '3',
        source: 'staging.mysql.com',
        target: 'prod.mysql.com',
        timestamp: new Date(Date.now() - 172800000), // 2 days ago
        differenceCount: 3,
      },
    ]
    setRecentComparisons(mockData)
  }, [])

  if (recentComparisons.length === 0) {
    return null
  }

  return (
    <div className="rounded-lg border bg-card p-6">
      <div className="mb-4 flex items-center gap-2">
        <Clock className="h-5 w-5 text-primary" />
        <h2 className="text-lg font-semibold">Recent Comparisons</h2>
      </div>

      <div className="space-y-3">
        {recentComparisons.map((comparison) => (
          <div
            key={comparison.id}
            className="flex items-center justify-between rounded-lg border p-4 hover:bg-accent/50 cursor-pointer"
          >
            <div className="flex items-center gap-3">
              <Database className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium">
                  {comparison.source} → {comparison.target}
                </p>
                <p className="text-xs text-muted-foreground">
                  {formatDistanceToNow(comparison.timestamp, { addSuffix: true })}
                </p>
              </div>
            </div>
            
            <div className="text-right">
              <p className="text-2xl font-bold">{comparison.differenceCount}</p>
              <p className="text-xs text-muted-foreground">differences</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
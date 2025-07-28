'use client'

import { useState, useEffect } from 'react'
import { Clock, Database } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { getRecentComparisons } from '@/lib/api'
import { toast } from 'react-hot-toast'

interface RecentComparison {
  id: string
  source: {
    display_name: string
  }
  target: {
    display_name: string
  }
  timestamp: string
  difference_count: number
}

export function RecentComparisons() {
  const [recentComparisons, setRecentComparisons] = useState<RecentComparison[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchRecentComparisons()
  }, [])

  const fetchRecentComparisons = async () => {
    try {
      const data = await getRecentComparisons(5)
      setRecentComparisons(data)
    } catch (error) {
      console.error('Failed to fetch recent comparisons:', error)
      // Don't show error toast if it's just that there's no history yet
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="rounded-lg border bg-card p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-muted rounded w-1/3 mb-4"></div>
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-20 bg-muted rounded"></div>
            ))}
          </div>
        </div>
      </div>
    )
  }

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
                  {comparison.source.display_name} → {comparison.target.display_name}
                </p>
                <p className="text-xs text-muted-foreground">
                  {formatDistanceToNow(new Date(comparison.timestamp), { addSuffix: true })}
                </p>
              </div>
            </div>
            
            <div className="text-right">
              <p className="text-2xl font-bold">{comparison.difference_count}</p>
              <p className="text-xs text-muted-foreground">differences</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
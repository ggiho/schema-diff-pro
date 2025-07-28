'use client'

import { useState } from 'react'
import { DatabaseSelector } from '@/components/DatabaseSelector'
import { ComparisonOptions } from '@/components/ComparisonOptions'
import { ComparisonProgress } from '@/components/ComparisonProgress'
import { ComparisonResults } from '@/components/ComparisonResults'
import { RecentComparisons } from '@/components/RecentComparisons'
import { Button } from '@/components/ui/button'
import { useComparisonStore } from '@/lib/store'
import { startComparison } from '@/lib/api'
import { toast } from 'react-hot-toast'
import { Database, Play } from 'lucide-react'

export default function HomePage() {
  const [isComparing, setIsComparing] = useState(false)
  const [comparisonId, setComparisonId] = useState<string | null>(null)
  const [showResults, setShowResults] = useState(false)
  
  const { 
    sourceConfig, 
    targetConfig, 
    comparisonOptions,
    setSourceConfig,
    setTargetConfig,
    setComparisonOptions 
  } = useComparisonStore()

  const handleStartComparison = async () => {
    if (!sourceConfig || !targetConfig) {
      toast.error('Please configure both source and target databases')
      return
    }

    setIsComparing(true)
    setShowResults(false)

    try {
      const result = await startComparison(sourceConfig, targetConfig, comparisonOptions)
      setComparisonId(result.comparison_id)
    } catch (error) {
      toast.error('Failed to start comparison')
      setIsComparing(false)
    }
  }

  const handleComparisonComplete = () => {
    setIsComparing(false)
    setShowResults(true)
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center gap-2">
            <Database className="h-8 w-8 text-primary" />
            <h1 className="text-2xl font-bold">Schema Diff Pro</h1>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        {!isComparing && !showResults && (
          <>
            <div className="grid gap-8 md:grid-cols-2">
              <DatabaseSelector
                title="Source Database"
                config={sourceConfig}
                onConfigChange={setSourceConfig}
              />
              <DatabaseSelector
                title="Target Database"
                config={targetConfig}
                onConfigChange={setTargetConfig}
              />
            </div>

            <div className="mt-8">
              <ComparisonOptions
                options={comparisonOptions}
                onChange={setComparisonOptions}
              />
            </div>

            <div className="mt-8 flex justify-center">
              <Button
                size="lg"
                onClick={handleStartComparison}
                disabled={!sourceConfig || !targetConfig}
                className="gap-2"
              >
                <Play className="h-5 w-5" />
                Start Comparison
              </Button>
            </div>

            <div className="mt-12">
              <RecentComparisons />
            </div>
          </>
        )}

        {isComparing && comparisonId && (
          <ComparisonProgress
            comparisonId={comparisonId}
            onComplete={handleComparisonComplete}
          />
        )}

        {showResults && comparisonId && (
          <ComparisonResults
            comparisonId={comparisonId}
            onNewComparison={() => {
              setShowResults(false)
              setComparisonId(null)
            }}
          />
        )}
      </main>
    </div>
  )
}
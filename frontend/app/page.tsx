'use client'

import { useState, useEffect } from 'react'
import { DatabaseSelector } from '@/components/DatabaseSelector'
import { ComparisonOptions } from '@/components/ComparisonOptions'
import { ComparisonProgress } from '@/components/ComparisonProgress'
import { ComparisonResults } from '@/components/ComparisonResults'
import { RecentComparisons } from '@/components/RecentComparisons'
import { Button } from '@/components/ui/button'
import { useComparisonStore } from '@/lib/store'
import { startComparison } from '@/lib/api'
import { toast } from 'react-hot-toast'
import { Database, Play, RotateCcw } from 'lucide-react'

export default function HomePage() {
  const [isComparing, setIsComparing] = useState(false)
  const [isHydrated, setIsHydrated] = useState(false)
  
  const { 
    sourceConfig, 
    targetConfig, 
    comparisonOptions,
    currentComparisonId,
    currentComparisonResult,
    setSourceConfig,
    setTargetConfig,
    setComparisonOptions,
    setCurrentComparison,
    clearComparison
  } = useComparisonStore()

  // Handle hydration
  useEffect(() => {
    setIsHydrated(true)
  }, [])

  // Handle URL comparison parameter for rerun
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search)
      const urlComparisonId = params.get('comparison')
      if (urlComparisonId && urlComparisonId !== currentComparisonId) {
        // New comparison from rerun - clear old result and start watching new comparison
        setCurrentComparison(urlComparisonId, null)
        setIsComparing(true)
        // Clear URL parameter
        window.history.replaceState({}, '', '/')
      }
    }
  }, [currentComparisonId, setCurrentComparison])

  const handleStartComparison = async () => {
    if (!sourceConfig || !targetConfig) {
      toast.error('Please configure both source and target databases')
      return
    }

    setIsComparing(true)
    clearComparison() // Clear previous results

    try {
      const result = await startComparison(sourceConfig, targetConfig, comparisonOptions)
      setCurrentComparison(result.comparison_id, null)
    } catch (error) {
      toast.error('Failed to start comparison')
      setIsComparing(false)
    }
  }

  const handleComparisonComplete = (result: Parameters<typeof setCurrentComparison>[1]) => {
    setIsComparing(false)
    setCurrentComparison(currentComparisonId, result)
  }

  const handleNewComparison = () => {
    setIsComparing(false)
    clearComparison()
  }

  // Don't render until hydrated to prevent hydration mismatches
  if (!isHydrated) {
    return null
  }

  // Determine current view based on state
  const showResults = currentComparisonId && currentComparisonResult && !isComparing
  const showSetup = !isComparing && !showResults

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Database className="h-8 w-8 text-primary" />
              <h1 className="text-2xl font-bold">Schema Diff Pro</h1>
            </div>
            {showResults && (
              <Button
                variant="outline"
                onClick={handleNewComparison}
                className="gap-2"
              >
                <RotateCcw className="h-4 w-4" />
                New Comparison
              </Button>
            )}
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        {showSetup && (
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

        {isComparing && currentComparisonId && (
          <ComparisonProgress
            comparisonId={currentComparisonId}
            onComplete={handleComparisonComplete}
            onBack={handleNewComparison}
          />
        )}

        {showResults && currentComparisonId && (
          <ComparisonResults
            comparisonId={currentComparisonId}
            onNewComparison={handleNewComparison}
          />
        )}
      </main>
    </div>
  )
}
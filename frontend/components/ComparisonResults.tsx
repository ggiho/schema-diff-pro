'use client'

import { useState, useEffect } from 'react'
import { ComparisonResult, SeverityLevel } from '@/types'
import { getComparisonResult, generateSyncScript } from '@/lib/api'
import { Button } from './ui/button'
import { DiffViewer } from './DiffViewer'
import { SyncScriptViewer } from './SyncScriptViewer'
import { ResultsSummary } from './ResultsSummary'
import { DifferencesList } from './DifferencesList'
import { AlertCircle, Download, FileCode } from 'lucide-react'
import { toast } from 'react-hot-toast'

interface ComparisonResultsProps {
  comparisonId: string
  onNewComparison: () => void
}

export function ComparisonResults({ comparisonId, onNewComparison }: ComparisonResultsProps) {
  const [result, setResult] = useState<ComparisonResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'summary' | 'differences' | 'sync'>('summary')
  const [syncScript, setSyncScript] = useState<string | null>(null)
  const [generatingScript, setGeneratingScript] = useState(false)

  useEffect(() => {
    loadResults()
  }, [comparisonId])

  const loadResults = async () => {
    try {
      const data = await getComparisonResult(comparisonId)
      setResult(data)
    } catch (error) {
      toast.error('Failed to load comparison results')
    } finally {
      setLoading(false)
    }
  }

  const handleGenerateSyncScript = async () => {
    if (!result || result.differences.length === 0) {
      toast.error('No differences to sync')
      return
    }

    setGeneratingScript(true)
    try {
      const script = await generateSyncScript(comparisonId)
      setSyncScript(script.forward_script)
      setActiveTab('sync')
      toast.success('Sync script generated successfully')
    } catch (error) {
      console.error('Sync script generation error:', error)
      const errorMessage = error instanceof Error ? error.message : 'Failed to generate sync script'
      toast.error(errorMessage)
    } finally {
      setGeneratingScript(false)
    }
  }

  const downloadResults = () => {
    if (!result) return

    const data = JSON.stringify(result, null, 2)
    const blob = new Blob([data], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `comparison_${comparisonId}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  if (loading) {
    return <div className="text-center">Loading results...</div>
  }

  if (!result) {
    return (
      <div className="text-center">
        <AlertCircle className="mx-auto h-12 w-12 text-destructive" />
        <p className="mt-2">Failed to load results</p>
        <Button onClick={onNewComparison} className="mt-4">
          Start New Comparison
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Comparison Results</h2>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={downloadResults}>
            <Download className="mr-2 h-4 w-4" />
            Export Results
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleGenerateSyncScript}
            disabled={generatingScript || result.differences.length === 0}
          >
            <FileCode className="mr-2 h-4 w-4" />
            {generatingScript ? 'Generating...' : 'Generate Sync Script'}
          </Button>
        </div>
      </div>

      <div className="border-b">
        <nav className="flex gap-4">
          {[
            { id: 'summary', label: 'Summary' },
            { id: 'differences', label: 'Differences' },
            { id: 'sync', label: 'Sync Script' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={cn(
                'border-b-2 px-4 py-2 text-sm font-medium transition-colors',
                activeTab === tab.id
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              )}
            >
              {tab.label}
              {tab.id === 'differences' && result.differences.length > 0 && (
                <span className="ml-2 rounded-full bg-primary px-2 py-0.5 text-xs text-primary-foreground">
                  {result.differences.length}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      <div className="min-h-[500px]">
        {activeTab === 'summary' && <ResultsSummary result={result} />}
        {activeTab === 'differences' && <DifferencesList differences={result.differences} />}
        {activeTab === 'sync' && (
          syncScript ? (
            <SyncScriptViewer script={syncScript} />
          ) : (
            <div className="text-center text-muted-foreground">
              <FileCode className="mx-auto h-12 w-12 text-muted-foreground/50" />
              <p className="mt-2">No sync script generated yet</p>
              <Button onClick={handleGenerateSyncScript} className="mt-4" disabled={result.differences.length === 0}>
                Generate Sync Script
              </Button>
            </div>
          )
        )}
      </div>
    </div>
  )
}

function cn(...classes: string[]) {
  return classes.filter(Boolean).join(' ')
}
'use client'

import { useState, useEffect } from 'react'
import { ComparisonResult, SeverityLevel, SyncDirection, ScriptAnalysisResponse, ExecuteScriptResponse } from '@/types'
import { getComparisonResult, generateSyncScript, analyzeScript, executeScript, rerunComparison } from '@/lib/api'
import { Button } from './ui/button'
import { DiffViewer } from './DiffViewer'
import { SyncScriptViewer } from './SyncScriptViewer'
import { ResultsSummary } from './ResultsSummary'
import { DifferencesList } from './DifferencesList'
import { AlertCircle, Download, FileCode, ArrowRight, Play, AlertTriangle, CheckCircle, XCircle, Loader2, RefreshCw } from 'lucide-react'
import { toast } from 'react-hot-toast'

interface ComparisonResultsProps {
  comparisonId: string
  onNewComparison: () => void
}

export function ComparisonResults({ comparisonId, onNewComparison }: ComparisonResultsProps) {
  const [result, setResult] = useState<ComparisonResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'summary' | 'differences' | 'sync'>('summary')
  const [generatingScript, setGeneratingScript] = useState(false)
  const [syncDirection, setSyncDirection] = useState<SyncDirection>(SyncDirection.SOURCE_TO_TARGET)
  
  // Cache scripts by direction to avoid regenerating
  const [scriptCache, setScriptCache] = useState<{
    [SyncDirection.SOURCE_TO_TARGET]?: string
    [SyncDirection.TARGET_TO_SOURCE]?: string
  }>({})
  
  // Execute script state
  const [showExecuteDialog, setShowExecuteDialog] = useState(false)
  const [scriptAnalysis, setScriptAnalysis] = useState<ScriptAnalysisResponse | null>(null)
  const [executing, setExecuting] = useState(false)
  const [executeResult, setExecuteResult] = useState<ExecuteScriptResponse | null>(null)

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

  const handleGenerateSyncScript = async (direction: SyncDirection) => {
    if (!result || result.differences.length === 0) {
      toast.error('No differences to sync')
      return
    }

    // Check cache first
    if (scriptCache[direction]) {
      setSyncDirection(direction)
      setActiveTab('sync')
      return
    }

    setGeneratingScript(true)
    setSyncDirection(direction)
    try {
      const script = await generateSyncScript(comparisonId, direction)
      // Cache the generated script
      setScriptCache(prev => ({
        ...prev,
        [direction]: script.forward_script
      }))
      setActiveTab('sync')
      const directionText = direction === SyncDirection.SOURCE_TO_TARGET 
        ? 'Source → Target' 
        : 'Target → Source'
      toast.success(`Sync script generated (${directionText})`)
    } catch (error) {
      console.error('Sync script generation error:', error)
      const errorMessage = error instanceof Error ? error.message : 'Failed to generate sync script'
      toast.error(errorMessage)
    } finally {
      setGeneratingScript(false)
    }
  }
  
  // Get current script from cache
  const currentScript = scriptCache[syncDirection]
  
  // Get target database based on direction
  const getTargetDatabase = (): 'source' | 'target' => {
    return syncDirection === SyncDirection.SOURCE_TO_TARGET ? 'target' : 'source'
  }
  
  const handleApplyScript = async () => {
    if (!currentScript) return
    
    const targetDb = getTargetDatabase()
    
    try {
      // First analyze the script for risks
      const analysis = await analyzeScript(comparisonId, currentScript, targetDb)
      setScriptAnalysis(analysis)
      setExecuteResult(null)
      setShowExecuteDialog(true)
    } catch (error) {
      console.error('Script analysis error:', error)
      toast.error('Failed to analyze script')
    }
  }
  
  const [rerunning, setRerunning] = useState(false)
  
  const handleConfirmExecute = async () => {
    if (!currentScript || !scriptAnalysis) return
    
    setExecuting(true)
    try {
      const execResult = await executeScript(comparisonId, currentScript, scriptAnalysis.target_database)
      setExecuteResult(execResult)
      
      if (execResult.success) {
        toast.success(`Successfully executed ${execResult.executed_statements} statements`)
        // Clear script cache since DB changed
        setScriptCache({})
      } else {
        toast.error(`Execution completed with ${execResult.failed_statements} failures`)
      }
    } catch (error: any) {
      console.error('Script execution error:', error)
      const errorMessage = error?.response?.data?.detail
        || error?.message
        || 'Failed to execute script'
      toast.error(`Execution failed: ${errorMessage}`)
    } finally {
      setExecuting(false)
    }
  }
  
  const handleRerunComparison = async () => {
    setRerunning(true)
    try {
      const response = await rerunComparison(comparisonId)
      toast.success('Re-running comparison...')
      // Redirect to new comparison page
      window.location.href = `/?comparison=${response.comparison_id}`
    } catch (error) {
      console.error('Rerun comparison error:', error)
      toast.error('Failed to re-run comparison')
    } finally {
      setRerunning(false)
    }
  }

  const downloadResults = () => {
    if (!result) return

    // SECURITY: Remove sensitive data before export
    const sanitizedResult = {
      ...result,
      // Remove entire config objects to prevent any credential leakage
      source_config: {
        host: result.source_config.host,
        port: result.source_config.port,
        database: result.source_config.database,
        // DO NOT include user, password, or SSH tunnel info
      },
      target_config: {
        host: result.target_config.host,
        port: result.target_config.port,
        database: result.target_config.database,
        // DO NOT include user, password, or SSH tunnel info
      }
    }

    const data = JSON.stringify(sanitizedResult, null, 2)
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
          currentScript ? (
            <div className="space-y-4">
              {/* Direction selector */}
              <div className="flex items-center justify-between rounded-lg border bg-muted/50 p-3">
                <div className="flex items-center gap-2 text-sm">
                  <span className="font-medium">Direction:</span>
                  {syncDirection === SyncDirection.SOURCE_TO_TARGET ? (
                    <>
                      <span className="text-blue-600 dark:text-blue-400">Source</span>
                      <ArrowRight className="h-4 w-4" />
                      <span className="text-green-600 dark:text-green-400">Target</span>
                      <span className="text-muted-foreground ml-2">(Target will be modified)</span>
                    </>
                  ) : (
                    <>
                      <span className="text-green-600 dark:text-green-400">Target</span>
                      <ArrowRight className="h-4 w-4" />
                      <span className="text-blue-600 dark:text-blue-400">Source</span>
                      <span className="text-muted-foreground ml-2">(Source will be modified)</span>
                    </>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex rounded-md border">
                    <Button
                      variant={syncDirection === SyncDirection.SOURCE_TO_TARGET ? "default" : "ghost"}
                      size="sm"
                      className="rounded-r-none"
                      onClick={() => handleGenerateSyncScript(SyncDirection.SOURCE_TO_TARGET)}
                      disabled={generatingScript}
                    >
                      Source → Target
                    </Button>
                    <Button
                      variant={syncDirection === SyncDirection.TARGET_TO_SOURCE ? "default" : "ghost"}
                      size="sm"
                      className="rounded-l-none border-l"
                      onClick={() => handleGenerateSyncScript(SyncDirection.TARGET_TO_SOURCE)}
                      disabled={generatingScript}
                    >
                      Target → Source
                    </Button>
                  </div>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={handleApplyScript}
                    className="ml-4"
                  >
                    <Play className="h-4 w-4 mr-2" />
                    Apply to {getTargetDatabase().charAt(0).toUpperCase() + getTargetDatabase().slice(1)} DB
                  </Button>
                </div>
              </div>
              <SyncScriptViewer script={currentScript} />
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <FileCode className="h-16 w-16 text-muted-foreground/30" />
              <h3 className="mt-4 text-lg font-medium text-foreground">Generate Sync Script</h3>
              <p className="mt-1 text-sm">Choose which database should be modified</p>
              
              <div className="mt-6 flex gap-4">
                <Button 
                  onClick={() => handleGenerateSyncScript(SyncDirection.SOURCE_TO_TARGET)} 
                  disabled={result.differences.length === 0 || generatingScript}
                  variant="default"
                  size="lg"
                  className="flex-col h-auto py-4 px-6"
                >
                  <div className="flex items-center gap-2 text-base">
                    <span>Source</span>
                    <ArrowRight className="h-4 w-4" />
                    <span>Target</span>
                  </div>
                  <span className="text-xs font-normal opacity-80 mt-1">
                    Modify Target to match Source
                  </span>
                </Button>
                <Button 
                  onClick={() => handleGenerateSyncScript(SyncDirection.TARGET_TO_SOURCE)} 
                  disabled={result.differences.length === 0 || generatingScript}
                  variant="outline"
                  size="lg"
                  className="flex-col h-auto py-4 px-6"
                >
                  <div className="flex items-center gap-2 text-base">
                    <span>Target</span>
                    <ArrowRight className="h-4 w-4" />
                    <span>Source</span>
                  </div>
                  <span className="text-xs font-normal opacity-80 mt-1">
                    Modify Source to match Target
                  </span>
                </Button>
              </div>
              
              {generatingScript && (
                <p className="mt-4 text-sm">Generating script...</p>
              )}
              
              {result.differences.length === 0 && (
                <p className="mt-4 text-sm text-yellow-600 dark:text-yellow-400">
                  No differences found to generate script
                </p>
              )}
            </div>
          )
        )}
      </div>
      
      {/* Execute Script Dialog */}
      {showExecuteDialog && scriptAnalysis && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-background rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center gap-3 mb-4">
                {scriptAnalysis.risks.risk_level === 'high' ? (
                  <AlertTriangle className="h-8 w-8 text-red-500" />
                ) : scriptAnalysis.risks.risk_level === 'medium' ? (
                  <AlertTriangle className="h-8 w-8 text-yellow-500" />
                ) : (
                  <AlertCircle className="h-8 w-8 text-blue-500" />
                )}
                <div>
                  <h2 className="text-xl font-bold">
                    {executeResult ? 'Execution Result' : 'Confirm Script Execution'}
                  </h2>
                  <p className="text-sm text-muted-foreground">
                    Target: {scriptAnalysis.target_database.toUpperCase()} Database
                  </p>
                </div>
              </div>
              
              {!executeResult ? (
                <>
                  {/* Risk Analysis */}
                  <div className={cn(
                    "rounded-lg border p-4 mb-4",
                    scriptAnalysis.risks.risk_level === 'high' 
                      ? "border-red-500 bg-red-50 dark:bg-red-950/20" 
                      : scriptAnalysis.risks.risk_level === 'medium'
                        ? "border-yellow-500 bg-yellow-50 dark:bg-yellow-950/20"
                        : "border-blue-500 bg-blue-50 dark:bg-blue-950/20"
                  )}>
                    <div className="flex items-center gap-2 mb-2">
                      <span className={cn(
                        "px-2 py-1 rounded text-xs font-bold uppercase",
                        scriptAnalysis.risks.risk_level === 'high' 
                          ? "bg-red-500 text-white" 
                          : scriptAnalysis.risks.risk_level === 'medium'
                            ? "bg-yellow-500 text-white"
                            : "bg-blue-500 text-white"
                      )}>
                        {scriptAnalysis.risks.risk_level} Risk
                      </span>
                    </div>
                    
                    {scriptAnalysis.risks.warnings.length > 0 && (
                      <div className="space-y-1">
                        {scriptAnalysis.risks.warnings.map((warning, i) => (
                          <div key={i} className="flex items-start gap-2 text-sm">
                            <AlertTriangle className="h-4 w-4 text-yellow-600 flex-shrink-0 mt-0.5" />
                            <span>{warning}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    
                    {scriptAnalysis.risks.drop_tables.length > 0 && (
                      <div className="mt-3 p-3 border-2 border-red-400 rounded bg-white dark:bg-gray-800">
                        <p className="text-sm font-bold text-red-600 dark:text-red-400">
                          ⚠️ Tables to be DROPPED (DATA WILL BE LOST):
                        </p>
                        <ul className="mt-1 text-sm text-red-600 dark:text-red-300">
                          {scriptAnalysis.risks.drop_tables.map((table, i) => (
                            <li key={i} className="font-mono">• {table}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    
                    {scriptAnalysis.risks.drop_columns.length > 0 && (
                      <div className="mt-3 p-3 border-2 border-orange-400 rounded bg-white dark:bg-gray-800">
                        <p className="text-sm font-bold text-orange-600 dark:text-orange-400">
                          ⚠️ Columns to be DROPPED:
                        </p>
                        <ul className="mt-1 text-sm text-orange-600 dark:text-orange-300">
                          {scriptAnalysis.risks.drop_columns.map((col, i) => (
                            <li key={i} className="font-mono">• {col}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                  
                  <p className="text-sm text-muted-foreground mb-4">
                    This will execute the sync script directly on the {scriptAnalysis.target_database} database.
                    Make sure you have a backup before proceeding.
                  </p>
                </>
              ) : (
                <>
                  {/* Execution Result */}
                  <div className={cn(
                    "rounded-lg border p-4 mb-4",
                    executeResult.success 
                      ? "border-green-500 bg-green-50 dark:bg-green-950/20" 
                      : "border-red-500 bg-red-50 dark:bg-red-950/20"
                  )}>
                    <div className="flex items-center gap-2 mb-3">
                      {executeResult.success ? (
                        <CheckCircle className="h-6 w-6 text-green-500" />
                      ) : (
                        <XCircle className="h-6 w-6 text-red-500" />
                      )}
                      <span className="font-bold">
                        {executeResult.success ? 'Execution Successful' : 'Execution Completed with Errors'}
                      </span>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <span className="text-muted-foreground">Executed:</span>
                        <span className="ml-2 font-mono text-green-600">{executeResult.executed_statements}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Failed:</span>
                        <span className="ml-2 font-mono text-red-600">{executeResult.failed_statements}</span>
                      </div>
                    </div>
                  </div>
                  
                  {executeResult.errors.length > 0 && (
                    <div className="rounded-lg border border-red-300 bg-red-50 dark:bg-red-950/20 p-4 mb-4">
                      <h4 className="font-bold text-red-700 dark:text-red-400 mb-2">Errors:</h4>
                      <ul className="space-y-1 text-sm text-red-600 dark:text-red-300">
                        {executeResult.errors.map((error, i) => (
                          <li key={i} className="font-mono text-xs">{error}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  
                  {executeResult.results.some(r => !r.success) && (
                    <div className="rounded-lg border p-4 mb-4 max-h-48 overflow-y-auto">
                      <h4 className="font-bold mb-2">Statement Results:</h4>
                      <div className="space-y-2">
                        {executeResult.results.map((stmt, i) => (
                          <div key={i} className={cn(
                            "text-xs p-2 rounded font-mono",
                            stmt.success ? "bg-green-50 dark:bg-green-950/20" : "bg-red-50 dark:bg-red-950/20"
                          )}>
                            <div className="flex items-center gap-2">
                              {stmt.success ? (
                                <CheckCircle className="h-3 w-3 text-green-500" />
                              ) : (
                                <XCircle className="h-3 w-3 text-red-500" />
                              )}
                              <span className={stmt.success ? "truncate" : "break-all"}>
                                {stmt.success ? stmt.statement : (stmt.full_statement || stmt.statement)}
                              </span>
                            </div>
                            {stmt.error && (
                              <p className="mt-1 text-red-600 dark:text-red-400 pl-5 break-words">{stmt.error}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
              
              <div className="flex justify-end gap-3 mt-6">
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowExecuteDialog(false)
                    setScriptAnalysis(null)
                    setExecuteResult(null)
                  }}
                >
                  {executeResult ? 'Close' : 'Cancel'}
                </Button>
                {executeResult && executeResult.success && (
                  <Button
                    onClick={handleRerunComparison}
                    disabled={rerunning}
                  >
                    {rerunning ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Re-running...
                      </>
                    ) : (
                      <>
                        <RefreshCw className="h-4 w-4 mr-2" />
                        Re-run Comparison
                      </>
                    )}
                  </Button>
                )}
                {!executeResult && (
                  <Button
                    variant={scriptAnalysis.risks.risk_level === 'high' ? 'destructive' : 'default'}
                    onClick={handleConfirmExecute}
                    disabled={executing}
                  >
                    {executing ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Executing...
                      </>
                    ) : (
                      <>
                        <Play className="h-4 w-4 mr-2" />
                        {scriptAnalysis.risks.risk_level === 'high' 
                          ? 'Execute Anyway (Dangerous!)' 
                          : 'Execute Script'}
                      </>
                    )}
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function cn(...classes: string[]) {
  return classes.filter(Boolean).join(' ')
}
'use client'

import { useEffect, useState } from 'react'
import { ComparisonProgress as ComparisonProgressType } from '@/types'
import { Progress } from './ui/progress'
import { Loader2 } from 'lucide-react'
import { getComparisonStatus, getComparisonResult } from '@/lib/api'
import { toast } from 'react-hot-toast'

interface ComparisonProgressProps {
  comparisonId: string
  onComplete: (result?: any) => void
}

export function ComparisonProgress({ comparisonId, onComplete }: ComparisonProgressProps) {
  const [progress, setProgress] = useState<ComparisonProgressType | null>(null)
  const [status, setStatus] = useState<'running' | 'completed' | 'failed'>('running')

  useEffect(() => {
    console.log('ComparisonProgress mounted for:', comparisonId)
    let ws: WebSocket | null = null
    let pollInterval: NodeJS.Timeout | null = null
    let isCleanedUp = false

    // Start polling immediately as primary method
    const startPolling = () => {
      console.log('Starting status polling for:', comparisonId)
      
      // Check status immediately
      getComparisonStatus(comparisonId)
        .then(async statusResponse => {
          console.log('Initial status check:', statusResponse)
          if (statusResponse.status === 'completed') {
            setStatus('completed')
            toast.success('Comparison completed successfully!')
            
            // Fetch the comparison result and pass it to onComplete
            try {
              const result = await getComparisonResult(comparisonId)
              setTimeout(() => {
                if (!isCleanedUp) {
                  onComplete(result)
                }
              }, 1000)
            } catch (error) {
              console.error('Failed to fetch comparison result:', error)
              setTimeout(() => {
                if (!isCleanedUp) {
                  onComplete()
                }
              }, 1000)
            }
            return
          }
        })
        .catch(error => {
          console.error('Failed to check initial status:', error)
        })

      // Continue polling
      pollInterval = setInterval(async () => {
        try {
          const statusResponse = await getComparisonStatus(comparisonId)
          console.log('Poll status:', statusResponse)
          
          if (statusResponse.status === 'completed') {
            clearInterval(pollInterval!)
            setStatus('completed')
            toast.success('Comparison completed successfully!')
            
            // Fetch the comparison result and pass it to onComplete
            try {
              const result = await getComparisonResult(comparisonId)
              setTimeout(() => {
                if (!isCleanedUp) {
                  onComplete(result)
                }
              }, 1000)
            } catch (error) {
              console.error('Failed to fetch comparison result:', error)
              setTimeout(() => {
                if (!isCleanedUp) {
                  onComplete()
                }
              }, 1000)
            }
          } else if (statusResponse.status === 'failed') {
            clearInterval(pollInterval!)
            setStatus('failed')
            toast.error('Comparison failed')
          }
        } catch (error) {
          console.error('Failed to poll status:', error)
        }
      }, 1000) // Poll every second
    }

    // Try WebSocket for real-time updates
    const connectWebSocket = () => {
      try {
        const wsUrl = `ws://localhost:8000/ws/comparison/${comparisonId}`
        console.log('Connecting to WebSocket:', wsUrl)
        ws = new WebSocket(wsUrl)

        ws.onopen = () => {
          console.log('WebSocket connected')
        }

        ws.onmessage = async (event) => {
          try {
            const data = JSON.parse(event.data)
            console.log('WebSocket message:', data)
            
            if (data.type === 'progress') {
              setProgress(data.data)
            } else if (data.type === 'complete') {
              console.log('Received complete message via WebSocket')
              if (pollInterval) {
                clearInterval(pollInterval)
              }
              setStatus('completed')
              toast.success('Comparison completed successfully!')
              
              // Fetch the comparison result and pass it to onComplete
              try {
                const result = await getComparisonResult(comparisonId)
                setTimeout(() => {
                  if (!isCleanedUp) {
                    onComplete(result)
                  }
                }, 1000)
              } catch (error) {
                console.error('Failed to fetch comparison result via WebSocket:', error)
                setTimeout(() => {
                  if (!isCleanedUp) {
                    onComplete()
                  }
                }, 1000)
              }
            } else if (data.type === 'error') {
              if (pollInterval) {
                clearInterval(pollInterval)
              }
              setStatus('failed')
              toast.error(`Comparison failed: ${data.message}`)
            }
          } catch (e) {
            console.error('Failed to parse WebSocket message:', e)
          }
        }

        ws.onerror = (error) => {
          console.error('WebSocket error:', error)
        }

        ws.onclose = () => {
          console.log('WebSocket closed')
        }
      } catch (error) {
        console.error('Failed to connect WebSocket:', error)
      }
    }

    // Start both polling and WebSocket
    startPolling()
    connectWebSocket()

    // Cleanup
    return () => {
      console.log('Cleaning up ComparisonProgress')
      isCleanedUp = true
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close()
      }
      if (pollInterval) {
        clearInterval(pollInterval)
      }
    }
  }, [comparisonId, onComplete])

  const progressPercentage = progress
    ? Math.round((progress.current / progress.total) * 100)
    : 0

  return (
    <div className="mx-auto max-w-2xl">
      <div className="rounded-lg border bg-card p-8">
        <div className="mb-6 text-center">
          <Loader2 className="mx-auto mb-4 h-12 w-12 animate-spin text-primary" />
          <h2 className="text-2xl font-semibold">Comparing Databases</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            This may take a few moments depending on the database size
          </p>
        </div>

        <div className="space-y-4">
          <div>
            <div className="mb-2 flex justify-between text-sm">
              <span className="font-medium capitalize">
                {progress?.phase || 'Initializing'}
              </span>
              <span className="text-muted-foreground">
                {progress ? `${progress.current} / ${progress.total}` : '...'}
              </span>
            </div>
            <Progress value={progressPercentage} className="h-2" />
          </div>

          {progress?.current_object && (
            <p className="text-sm text-muted-foreground">
              Currently processing: <span className="font-medium">{progress.current_object}</span>
            </p>
          )}

          {progress?.message && (
            <p className="text-sm text-muted-foreground">{progress.message}</p>
          )}

          {progress?.estimated_time_remaining && (
            <p className="text-sm text-muted-foreground">
              Estimated time remaining: {Math.ceil(progress.estimated_time_remaining / 60)} minutes
            </p>
          )}
        </div>

        {status === 'failed' && (
          <div className="mt-6 rounded-md bg-destructive/10 p-4">
            <p className="text-sm text-destructive">
              The comparison failed. Please check your database connections and try again.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
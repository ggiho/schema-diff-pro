'use client'

import { useState, useEffect } from 'react'
import { DatabaseConfig } from '@/types'
import { Button } from './ui/button'
import { Database, TestTube, CheckCircle, XCircle } from 'lucide-react'
import { toast } from 'react-hot-toast'

interface DatabaseSelectorProps {
  title: string
  config: DatabaseConfig | null
  onConfigChange: (config: DatabaseConfig) => void
}

interface ConnectionState {
  status: 'idle' | 'testing' | 'connected' | 'failed'
  connectedDatabase?: string
  lastTestedConfig?: DatabaseConfig
}

export function DatabaseSelector({ title, config, onConfigChange }: DatabaseSelectorProps) {
  const [formData, setFormData] = useState<DatabaseConfig>(
    config || {
      host: 'localhost',
      port: 3306,
      user: 'root',
      password: '',
      database: '',
    }
  )
  const [connectionState, setConnectionState] = useState<ConnectionState>({
    status: 'idle'
  })

  // Check if configuration has changed significantly
  const hasConfigChanged = () => {
    if (!connectionState.lastTestedConfig) return false
    const last = connectionState.lastTestedConfig
    return last.host !== formData.host || 
           last.port !== formData.port || 
           last.user !== formData.user || 
           last.password !== formData.password ||
           last.database !== formData.database
  }

  // Reset connection state when config changes
  useEffect(() => {
    if (hasConfigChanged() && connectionState.status === 'connected') {
      setConnectionState({ status: 'idle' })
    }
  }, [formData])

  const handleChange = (field: keyof DatabaseConfig, value: string | number) => {
    const newData = { ...formData, [field]: value }
    setFormData(newData)
    onConfigChange(newData)
  }

  const testConnection = async () => {
    setConnectionState({ status: 'testing' })
    
    try {
      const response = await fetch('/api/v1/database/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      })

      const result = await response.json()

      if (response.ok) {
        const databaseName = result.database || formData.database || 'MySQL'
        setConnectionState({
          status: 'connected',
          connectedDatabase: databaseName,
          lastTestedConfig: { ...formData }
        })
        toast.success(`Connected to ${databaseName}!`)
      } else {
        setConnectionState({ 
          status: 'failed',
          lastTestedConfig: { ...formData }
        })
        toast.error(result.detail || `Failed to connect to ${title}`)
      }
    } catch (error) {
      setConnectionState({ 
        status: 'failed',
        lastTestedConfig: { ...formData }
      })
      toast.error(`Connection failed: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  return (
    <div className="rounded-lg border bg-card p-6">
      <div className="mb-4 flex items-center gap-2">
        <Database className="h-5 w-5 text-primary" />
        <h2 className="text-lg font-semibold">{title}</h2>
      </div>

      <div className="space-y-4">
        <div>
          <label className="text-sm font-medium">Host</label>
          <input
            type="text"
            value={formData.host}
            onChange={(e) => handleChange('host', e.target.value)}
            className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm"
            placeholder="localhost"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-medium">Port</label>
            <input
              type="number"
              value={formData.port}
              onChange={(e) => handleChange('port', parseInt(e.target.value) || 3306)}
              className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm"
              placeholder="3306"
            />
          </div>
          <div>
            <label className="text-sm font-medium">Database (Optional)</label>
            <input
              type="text"
              value={formData.database}
              onChange={(e) => handleChange('database', e.target.value)}
              className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm"
              placeholder="Leave empty for all"
            />
          </div>
        </div>

        <div>
          <label className="text-sm font-medium">Username</label>
          <input
            type="text"
            value={formData.user}
            onChange={(e) => handleChange('user', e.target.value)}
            className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm"
            placeholder="root"
          />
        </div>

        <div>
          <label className="text-sm font-medium">Password</label>
          <input
            type="password"
            value={formData.password}
            onChange={(e) => handleChange('password', e.target.value)}
            className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm"
            placeholder="••••••••"
          />
        </div>

        <Button
          variant={connectionState.status === 'connected' ? 'default' : 'outline'}
          size="sm"
          onClick={testConnection}
          disabled={connectionState.status === 'testing'}
          className={`w-full transition-all ${
            connectionState.status === 'connected' ? 'bg-green-600 hover:bg-green-700 text-white' : 
            connectionState.status === 'failed' ? 'border-red-500 text-red-500 hover:bg-red-50' : ''
          }`}
        >
          {connectionState.status === 'testing' ? (
            <>
              <TestTube className="mr-2 h-4 w-4 animate-pulse" />
              Testing...
            </>
          ) : connectionState.status === 'connected' ? (
            <>
              <CheckCircle className="mr-2 h-4 w-4" />
              Connected: {connectionState.connectedDatabase}
            </>
          ) : connectionState.status === 'failed' ? (
            <>
              <XCircle className="mr-2 h-4 w-4" />
              Test Connection
            </>
          ) : (
            <>
              <TestTube className="mr-2 h-4 w-4" />
              Test Connection
            </>
          )}
        </Button>
      </div>
    </div>
  )
}
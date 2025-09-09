'use client'

import { useState, useEffect } from 'react'
import { DatabaseConfigWithSSH, SSHTunnelConfig, SSHAuthMethod, TunnelStatus, SSHTunnelTestResult } from '@/types'
import { Button } from './ui/button'
import { Database, TestTube, CheckCircle, XCircle, Shield } from 'lucide-react'
import { toast } from 'react-hot-toast'
import { SSHTunnelConfig as SSHTunnelConfigComponent } from './ssh/SSHTunnelConfig'

interface DatabaseSelectorProps {
  title: string
  config: DatabaseConfigWithSSH | null
  onConfigChange: (config: DatabaseConfigWithSSH) => void
}

interface ConnectionState {
  status: 'idle' | 'testing' | 'connected' | 'failed'
  connectedDatabase?: string
  lastTestedConfig?: DatabaseConfigWithSSH
  sshTunnelStatus?: TunnelStatus
}

export function DatabaseSelector({ title, config, onConfigChange }: DatabaseSelectorProps) {
  const [formData, setFormData] = useState<DatabaseConfigWithSSH>(
    config || {
      host: 'localhost',
      port: 3306,
      user: 'root',
      password: '',
      database: '',
      ssh_tunnel: {
        enabled: false,
        ssh_host: '',
        ssh_port: 22,
        ssh_user: '',
        auth_method: SSHAuthMethod.PRIVATE_KEY,
        private_key_content: '',
        private_key_path: '',
        private_key_passphrase: '',
        remote_bind_host: 'localhost',
        remote_bind_port: 3306,
        connect_timeout: 30,
        keepalive_interval: 30,
        compression: false,
        strict_host_key_checking: false
      }
    }
  )
  const [connectionState, setConnectionState] = useState<ConnectionState>({
    status: 'idle'
  })

  // Check if configuration has changed significantly
  const hasConfigChanged = () => {
    if (!connectionState.lastTestedConfig) return false
    const last = connectionState.lastTestedConfig
    
    // Check database config changes
    const dbChanged = last.host !== formData.host || 
                     last.port !== formData.port || 
                     last.user !== formData.user || 
                     last.password !== formData.password ||
                     last.database !== formData.database
    
    // Check SSH tunnel config changes
    const sshChanged = last.ssh_tunnel?.enabled !== formData.ssh_tunnel?.enabled ||
                      (formData.ssh_tunnel?.enabled && (
                        last.ssh_tunnel?.ssh_host !== formData.ssh_tunnel?.ssh_host ||
                        last.ssh_tunnel?.ssh_port !== formData.ssh_tunnel?.ssh_port ||
                        last.ssh_tunnel?.ssh_user !== formData.ssh_tunnel?.ssh_user ||
                        last.ssh_tunnel?.auth_method !== formData.ssh_tunnel?.auth_method
                      ))
    
    return dbChanged || sshChanged
  }

  // Reset connection state when config changes
  useEffect(() => {
    if (hasConfigChanged() && connectionState.status === 'connected') {
      setConnectionState({ status: 'idle' })
    }
  }, [formData])

  const handleChange = (field: keyof DatabaseConfigWithSSH, value: string | number) => {
    const newData = { ...formData, [field]: value }
    setFormData(newData)
    onConfigChange(newData)
  }

  const handleSSHTunnelChange = (sshConfig: SSHTunnelConfig) => {
    const newData = { ...formData, ssh_tunnel: sshConfig }
    setFormData(newData)
    onConfigChange(newData)
  }

  const testSSHTunnel = async (sshConfig: SSHTunnelConfig): Promise<SSHTunnelTestResult> => {
    try {
      const testPayload = {
        config: sshConfig,
        test_database_connection: false,
        timeout_seconds: 30
      }
      
      const response = await fetch('/api/v1/ssh/tunnel/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(testPayload)
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'SSH tunnel test failed')
      }

      const result = await response.json()
      return result
    } catch (error) {
      throw new Error(error instanceof Error ? error.message : 'SSH tunnel test failed')
    }
  }

  const testConnection = async () => {
    setConnectionState({ status: 'testing' })
    
    try {
      const isSSHEnabled = formData.ssh_tunnel?.enabled
      const apiEndpoint = isSSHEnabled 
        ? '/api/v1/ssh/database/test-with-tunnel'
        : '/api/v1/database/test'
      
      const response = await fetch(apiEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      })

      const result = await response.json()

      if (response.ok) {
        const databaseName = result.database || formData.database || 'MySQL'
        const newConnectionState: ConnectionState = {
          status: 'connected',
          connectedDatabase: databaseName,
          lastTestedConfig: { ...formData }
        }
        
        // Add SSH tunnel status if SSH is enabled
        if (isSSHEnabled && result.tunnel_info) {
          newConnectionState.sshTunnelStatus = TunnelStatus.CONNECTED
        }
        
        setConnectionState(newConnectionState)
        
        if (isSSHEnabled) {
          toast.success(`Connected to ${databaseName} through SSH tunnel!`)
        } else {
          toast.success(`Connected to ${databaseName}!`)
        }
      } else {
        setConnectionState({ 
          status: 'failed',
          lastTestedConfig: { ...formData },
          sshTunnelStatus: isSSHEnabled ? TunnelStatus.FAILED : undefined
        })
        toast.error(result.detail || `Failed to connect to ${title}`)
      }
    } catch (error) {
      setConnectionState({ 
        status: 'failed',
        lastTestedConfig: { ...formData },
        sshTunnelStatus: formData.ssh_tunnel?.enabled ? TunnelStatus.FAILED : undefined
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

        {/* SSH Tunnel Section */}
        <div className="space-y-4 border-t pt-4">
          <div className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-primary" />
            <h3 className="text-md font-medium">SSH Tunnel (Optional)</h3>
          </div>
          
          <div className="flex items-center space-x-2">
            <input
              type="checkbox"
              id="ssh-enabled"
              checked={formData.ssh_tunnel?.enabled || false}
              onChange={(e) => handleSSHTunnelChange({
                ...formData.ssh_tunnel!,
                enabled: e.target.checked
              })}
              className="rounded border-gray-300 focus:ring-primary"
            />
            <label htmlFor="ssh-enabled" className="text-sm font-medium">
              Connect through SSH tunnel (bastion host/jump server)
            </label>
          </div>
          
          {formData.ssh_tunnel?.enabled && (
            <div className="mt-4 p-4 bg-muted/50 rounded-md">
              <SSHTunnelConfigComponent
                config={formData.ssh_tunnel}
                onChange={handleSSHTunnelChange}
                onTest={testSSHTunnel}
                showTitle={false}
              />
            </div>
          )}
          
          {/* Connection Status with SSH info */}
          {formData.ssh_tunnel?.enabled && connectionState.sshTunnelStatus && (
            <div className="flex items-center gap-2 text-sm">
              {connectionState.sshTunnelStatus === TunnelStatus.CONNECTED ? (
                <>
                  <CheckCircle className="h-4 w-4 text-green-600" />
                  <span className="text-green-600">SSH Tunnel Connected</span>
                </>
              ) : connectionState.sshTunnelStatus === TunnelStatus.FAILED ? (
                <>
                  <XCircle className="h-4 w-4 text-red-500" />
                  <span className="text-red-500">SSH Tunnel Failed</span>
                </>
              ) : null}
            </div>
          )}
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
              {formData.ssh_tunnel?.enabled ? 'Testing SSH + Database...' : 'Testing...'}
            </>
          ) : connectionState.status === 'connected' ? (
            <>
              <CheckCircle className="mr-2 h-4 w-4" />
              Connected: {connectionState.connectedDatabase}
              {formData.ssh_tunnel?.enabled && ' (via SSH)'}
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
// frontend/components/ssh/SSHTunnelConfig.tsx
'use client'

import { useState, useEffect } from 'react'
import { Button } from '../ui/button'
import { Checkbox } from '../ui/checkbox'
import { Input } from '../ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs'
import { Label } from '../ui/label'
import { Textarea } from '../ui/textarea'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'
import { Badge } from '../ui/badge'
import { Alert, AlertDescription } from '../ui/alert'
import { 
  Shield, 
  Key, 
  Server, 
  Lock, 
  Unlock,
  FileText,
  Upload,
  TestTube,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Info
} from 'lucide-react'
import { toast } from 'react-hot-toast'

interface SSHTunnelConfig {
  enabled: boolean
  ssh_host: string
  ssh_port: number
  ssh_user: string
  auth_method: 'password' | 'private_key' | 'ssh_agent'
  ssh_password?: string
  private_key_path?: string
  private_key_content?: string
  private_key_passphrase?: string
  key_type?: 'rsa' | 'ed25519' | 'ecdsa' | 'dsa'
  local_bind_port?: number
  remote_bind_host: string
  remote_bind_port: number
  connect_timeout: number
  keepalive_interval: number
  compression: boolean
  strict_host_key_checking: boolean
  known_hosts_path?: string
}

interface SSHTunnelConfigProps {
  config: SSHTunnelConfig
  onChange: (config: SSHTunnelConfig) => void
  onTest?: (config: SSHTunnelConfig) => Promise<boolean>
}

interface TunnelStatus {
  status: 'idle' | 'testing' | 'connected' | 'failed'
  message?: string
  errors?: string[]
  warnings?: string[]
  performance?: {
    ssh_connection_time_ms?: number
    database_connection_time_ms?: number
    tunnel_latency_ms?: number
  }
}

export function SSHTunnelConfig({ config, onChange, onTest }: SSHTunnelConfigProps) {
  const [tunnelStatus, setTunnelStatus] = useState<TunnelStatus>({ status: 'idle' })
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [keyFileContent, setKeyFileContent] = useState<string>('')

  const handleConfigChange = (field: keyof SSHTunnelConfig, value: any) => {
    const newConfig = { ...config, [field]: value }
    onChange(newConfig)
  }

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      const reader = new FileReader()
      reader.onload = (e) => {
        const content = e.target?.result as string
        setKeyFileContent(content)
        handleConfigChange('private_key_content', content)
        handleConfigChange('private_key_path', file.name)
      }
      reader.readAsText(file)
    }
  }

  const testTunnel = async () => {
    if (!onTest) return
    
    setTunnelStatus({ status: 'testing' })
    
    try {
      const result = await onTest(config)
      if (result) {
        setTunnelStatus({ 
          status: 'connected', 
          message: 'SSH tunnel connected successfully!' 
        })
        toast.success('SSH tunnel test successful!')
      } else {
        setTunnelStatus({ 
          status: 'failed', 
          message: 'SSH tunnel connection failed' 
        })
        toast.error('SSH tunnel test failed')
      }
    } catch (error) {
      setTunnelStatus({ 
        status: 'failed', 
        message: error instanceof Error ? error.message : 'Unknown error'
      })
      toast.error(`SSH tunnel test failed: ${error}`)
    }
  }

  const getStatusIcon = () => {
    switch (tunnelStatus.status) {
      case 'testing':
        return <TestTube className="h-4 w-4 animate-pulse" />
      case 'connected':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />
      default:
        return <Shield className="h-4 w-4" />
    }
  }

  const getStatusColor = () => {
    switch (tunnelStatus.status) {
      case 'testing':
        return 'border-blue-500'
      case 'connected':
        return 'border-green-500'
      case 'failed':
        return 'border-red-500'
      default:
        return ''
    }
  }

  return (
    <Card className={`transition-all ${getStatusColor()}`}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            {getStatusIcon()}
            <CardTitle className="text-lg">SSH Tunnel Configuration</CardTitle>
          </div>
          <div className="flex items-center space-x-2">
            <Checkbox
              id="ssh-enabled"
              checked={config.enabled}
              onCheckedChange={(checked) => handleConfigChange('enabled', checked)}
            />
            <Label htmlFor="ssh-enabled" className="text-sm font-medium">
              Enable SSH Tunnel
            </Label>
          </div>
        </div>
        <CardDescription>
          Securely connect to your database through an SSH tunnel (Jump Server)
        </CardDescription>
      </CardHeader>

      {config.enabled && (
        <CardContent className="space-y-6">
          {/* SSH Server Configuration */}
          <div className="space-y-4">
            <h3 className="text-md font-semibold flex items-center">
              <Server className="h-4 w-4 mr-2" />
              SSH Server Details
            </h3>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="md:col-span-2">
                <Label htmlFor="ssh-host">SSH Host</Label>
                <Input
                  id="ssh-host"
                  placeholder="jump-server.example.com"
                  value={config.ssh_host}
                  onChange={(e) => handleConfigChange('ssh_host', e.target.value)}
                />
              </div>
              
              <div>
                <Label htmlFor="ssh-port">SSH Port</Label>
                <Input
                  id="ssh-port"
                  type="number"
                  placeholder="22"
                  value={config.ssh_port}
                  onChange={(e) => handleConfigChange('ssh_port', parseInt(e.target.value) || 22)}
                />
              </div>
            </div>

            <div>
              <Label htmlFor="ssh-user">SSH Username</Label>
              <Input
                id="ssh-user"
                placeholder="ubuntu"
                value={config.ssh_user}
                onChange={(e) => handleConfigChange('ssh_user', e.target.value)}
              />
            </div>
          </div>

          {/* Authentication Method */}
          <div className="space-y-4">
            <h3 className="text-md font-semibold flex items-center">
              <Lock className="h-4 w-4 mr-2" />
              Authentication
            </h3>

            <Tabs 
              value={config.auth_method} 
              onValueChange={(value) => handleConfigChange('auth_method', value)}
            >
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="private_key">Private Key</TabsTrigger>
                <TabsTrigger value="password">Password</TabsTrigger>
                <TabsTrigger value="ssh_agent">SSH Agent</TabsTrigger>
              </TabsList>

              <TabsContent value="private_key" className="space-y-4">
                <div className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="key-file">Private Key File</Label>
                      <div className="flex space-x-2">
                        <Input
                          id="key-file"
                          type="file"
                          accept=".pem,.key,.pub"
                          onChange={handleFileUpload}
                          className="file:mr-4 file:py-1 file:px-4 file:rounded-md file:border-0 file:text-sm file:bg-primary file:text-primary-foreground"
                        />
                      </div>
                      <p className="text-xs text-muted-foreground mt-1">
                        Upload your SSH private key file (.pem, .key)
                      </p>
                    </div>

                    <div>
                      <Label htmlFor="key-type">Key Type</Label>
                      <Select 
                        value={config.key_type || ''} 
                        onValueChange={(value) => handleConfigChange('key_type', value)}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Auto-detect" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="rsa">RSA</SelectItem>
                          <SelectItem value="ed25519">Ed25519</SelectItem>
                          <SelectItem value="ecdsa">ECDSA</SelectItem>
                          <SelectItem value="dsa">DSA</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  {config.private_key_path && (
                    <div>
                      <Label htmlFor="key-passphrase">Private Key Passphrase (Optional)</Label>
                      <Input
                        id="key-passphrase"
                        type="password"
                        placeholder="Enter passphrase if key is encrypted"
                        value={config.private_key_passphrase || ''}
                        onChange={(e) => handleConfigChange('private_key_passphrase', e.target.value)}
                      />
                    </div>
                  )}

                  <div>
                    <Label htmlFor="key-content">Or paste private key content</Label>
                    <Textarea
                      id="key-content"
                      placeholder="-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC..."
                      value={keyFileContent}
                      onChange={(e) => {
                        setKeyFileContent(e.target.value)
                        handleConfigChange('private_key_content', e.target.value)
                      }}
                      rows={6}
                      className="font-mono text-sm"
                    />
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="password" className="space-y-4">
                <div>
                  <Label htmlFor="ssh-password">SSH Password</Label>
                  <Input
                    id="ssh-password"
                    type="password"
                    placeholder="Enter SSH password"
                    value={config.ssh_password || ''}
                    onChange={(e) => handleConfigChange('ssh_password', e.target.value)}
                  />
                  <Alert className="mt-2">
                    <AlertTriangle className="h-4 w-4" />
                    <AlertDescription>
                      Password authentication is less secure. Consider using SSH keys instead.
                    </AlertDescription>
                  </Alert>
                </div>
              </TabsContent>

              <TabsContent value="ssh_agent" className="space-y-4">
                <Alert>
                  <Info className="h-4 w-4" />
                  <AlertDescription>
                    Using SSH Agent for authentication. Make sure your SSH agent is running and has the required keys loaded.
                  </AlertDescription>
                </Alert>
              </TabsContent>
            </Tabs>
          </div>

          {/* Tunnel Configuration */}
          <div className="space-y-4">
            <h3 className="text-md font-semibold flex items-center">
              <Key className="h-4 w-4 mr-2" />
              Tunnel Settings
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <Label htmlFor="local-port">Local Port (Optional)</Label>
                <Input
                  id="local-port"
                  type="number"
                  placeholder="Auto-assign"
                  value={config.local_bind_port || ''}
                  onChange={(e) => handleConfigChange('local_bind_port', e.target.value ? parseInt(e.target.value) : undefined)}
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Leave empty to auto-assign available port
                </p>
              </div>

              <div>
                <Label htmlFor="remote-host">Remote Host</Label>
                <Input
                  id="remote-host"
                  placeholder="127.0.0.1"
                  value={config.remote_bind_host}
                  onChange={(e) => handleConfigChange('remote_bind_host', e.target.value)}
                />
              </div>

              <div>
                <Label htmlFor="remote-port">Remote Port</Label>
                <Input
                  id="remote-port"
                  type="number"
                  placeholder="3306"
                  value={config.remote_bind_port}
                  onChange={(e) => handleConfigChange('remote_bind_port', parseInt(e.target.value) || 3306)}
                />
              </div>
            </div>
          </div>

          {/* Advanced Settings */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-md font-semibold">Advanced Settings</h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowAdvanced(!showAdvanced)}
              >
                {showAdvanced ? 'Hide' : 'Show'} Advanced
              </Button>
            </div>

            {showAdvanced && (
              <div className="space-y-4 p-4 border rounded-lg bg-muted/20">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="connect-timeout">Connection Timeout (seconds)</Label>
                    <Input
                      id="connect-timeout"
                      type="number"
                      value={config.connect_timeout}
                      onChange={(e) => handleConfigChange('connect_timeout', parseInt(e.target.value) || 10)}
                    />
                  </div>

                  <div>
                    <Label htmlFor="keepalive-interval">Keepalive Interval (seconds)</Label>
                    <Input
                      id="keepalive-interval"
                      type="number"
                      value={config.keepalive_interval}
                      onChange={(e) => handleConfigChange('keepalive_interval', parseInt(e.target.value) || 30)}
                    />
                  </div>
                </div>

                <div className="flex items-center space-x-4">
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="compression"
                      checked={config.compression}
                      onCheckedChange={(checked) => handleConfigChange('compression', checked)}
                    />
                    <Label htmlFor="compression">Enable Compression</Label>
                  </div>

                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="host-key-checking"
                      checked={config.strict_host_key_checking}
                      onCheckedChange={(checked) => handleConfigChange('strict_host_key_checking', checked)}
                    />
                    <Label htmlFor="host-key-checking">Strict Host Key Checking</Label>
                  </div>
                </div>

                <div>
                  <Label htmlFor="known-hosts">Known Hosts File (Optional)</Label>
                  <Input
                    id="known-hosts"
                    placeholder="~/.ssh/known_hosts"
                    value={config.known_hosts_path || ''}
                    onChange={(e) => handleConfigChange('known_hosts_path', e.target.value)}
                  />
                </div>
              </div>
            )}
          </div>

          {/* Test Connection */}
          <div className="flex justify-between items-center pt-4 border-t">
            <div className="space-y-1">
              {tunnelStatus.message && (
                <p className={`text-sm ${
                  tunnelStatus.status === 'connected' ? 'text-green-600' :
                  tunnelStatus.status === 'failed' ? 'text-red-600' : 'text-gray-600'
                }`}>
                  {tunnelStatus.message}
                </p>
              )}
              {tunnelStatus.performance && (
                <div className="text-xs text-muted-foreground">
                  SSH: {tunnelStatus.performance.ssh_connection_time_ms}ms | 
                  DB: {tunnelStatus.performance.database_connection_time_ms}ms
                </div>
              )}
            </div>

            <Button
              onClick={testTunnel}
              disabled={tunnelStatus.status === 'testing' || !config.ssh_host || !config.ssh_user}
              variant={tunnelStatus.status === 'connected' ? 'default' : 'outline'}
              className={
                tunnelStatus.status === 'connected' ? 'bg-green-600 hover:bg-green-700' :
                tunnelStatus.status === 'failed' ? 'border-red-500 text-red-500' : ''
              }
            >
              {tunnelStatus.status === 'testing' ? (
                <>
                  <TestTube className="w-4 h-4 mr-2 animate-pulse" />
                  Testing...
                </>
              ) : tunnelStatus.status === 'connected' ? (
                <>
                  <CheckCircle className="w-4 h-4 mr-2" />
                  Connected
                </>
              ) : (
                <>
                  <TestTube className="w-4 h-4 mr-2" />
                  Test Tunnel
                </>
              )}
            </Button>
          </div>
        </CardContent>
      )}
    </Card>
  )
}


// Enhanced DatabaseSelector with SSH support
export function DatabaseSelectorWithSSH({ title, config, onConfigChange }: DatabaseSelectorProps) {
  const [dbConfig, setDbConfig] = useState<DatabaseConfigWithSSH>(
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
        auth_method: 'private_key',
        remote_bind_host: '127.0.0.1',
        remote_bind_port: 3306,
        connect_timeout: 10,
        keepalive_interval: 30,
        compression: true,
        strict_host_key_checking: true
      }
    }
  )

  // Handle database configuration changes
  const handleDbConfigChange = (field: keyof DatabaseConfigWithSSH, value: any) => {
    const newConfig = { ...dbConfig, [field]: value }
    setDbConfig(newConfig)
    onConfigChange(newConfig)
  }

  // Handle SSH tunnel configuration changes
  const handleSSHConfigChange = (sshConfig: SSHTunnelConfig) => {
    const newConfig = { ...dbConfig, ssh_tunnel: sshConfig }
    setDbConfig(newConfig)
    onConfigChange(newConfig)
  }

  // Test SSH tunnel connection
  const testSSHTunnel = async (sshConfig: SSHTunnelConfig): Promise<boolean> => {
    try {
      const response = await fetch('/api/v1/ssh/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: sshConfig, test_database_connection: true })
      })
      
      const result = await response.json()
      return response.ok && result.success
    } catch (error) {
      console.error('SSH tunnel test failed:', error)
      return false
    }
  }

  return (
    <div className="space-y-6">
      {/* SSH Tunnel Configuration */}
      <SSHTunnelConfig
        config={dbConfig.ssh_tunnel!}
        onChange={handleSSHConfigChange}
        onTest={testSSHTunnel}
      />

      {/* Original Database Configuration */}
      <Card>
        <CardHeader>
          <div className="flex items-center space-x-2">
            <Database className="h-5 w-5 text-primary" />
            <CardTitle>{title}</CardTitle>
          </div>
          <CardDescription>
            {dbConfig.ssh_tunnel?.enabled 
              ? "Database will be accessed through SSH tunnel" 
              : "Direct database connection"
            }
          </CardDescription>
        </CardHeader>
        
        <CardContent>
          {/* Original database form fields remain the same */}
          {/* ... existing database configuration UI ... */}
        </CardContent>
      </Card>
    </div>
  )
}
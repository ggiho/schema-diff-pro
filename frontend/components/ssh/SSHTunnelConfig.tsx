'use client'

import { useState, useRef, useEffect } from 'react'
import { Button } from '../ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'
import { Input } from '../ui/input'
import { Label } from '../ui/label'
import { Textarea } from '../ui/textarea'
import { Checkbox } from '../ui/checkbox'
import { Badge } from '../ui/badge'
import { Alert, AlertDescription } from '../ui/alert'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../ui/collapsible'
import { 
  Shield, 
  Key, 
  Server, 
  Lock, 
  Upload,
  TestTube,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Info,
  ChevronDown,
  ChevronUp
} from 'lucide-react'
import { toast } from 'react-hot-toast'

import {
  SSHTunnelConfig as SSHTunnelConfigType,
  SSHAuthMethod,
  TunnelStatus,
  SSHKeyType,
  SSHTunnelTestResult
} from '@/types'

interface SSHTunnelConfigProps {
  config: SSHTunnelConfigType
  onChange: (config: SSHTunnelConfigType) => void
  onTest?: (config: SSHTunnelConfigType) => Promise<SSHTunnelTestResult>
  disabled?: boolean
  showTitle?: boolean
}

interface TunnelTestStatus {
  status: 'idle' | 'testing' | 'connected' | 'failed'
  message?: string
  result?: SSHTunnelTestResult
}

export function SSHTunnelConfig({ config, onChange, onTest, disabled = false, showTitle = true }: SSHTunnelConfigProps) {
  const [testStatus, setTestStatus] = useState<TunnelTestStatus>({ status: 'idle' })
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [keyContent, setKeyContent] = useState<string>(config.private_key_content || '')
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Config prop이 변경되면 local state도 sync
  useEffect(() => {
    setKeyContent(config.private_key_content || '')
  }, [config.private_key_content])

  const handleConfigChange = (field: keyof SSHTunnelConfigType, value: any) => {
    if (disabled) return
    
    const newConfig = { ...config, [field]: value }
    if (onChange && typeof onChange === 'function') {
      onChange(newConfig)
    }
  }

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      const reader = new FileReader()
      reader.onload = (e) => {
        const content = e.target?.result as string
        
        // 즉시 parent config 업데이트 - 이게 가장 중요!
        const updatedConfig = {
          ...config,
          private_key_content: content,
          private_key_path: "" // Clear path when using content
        }
        
        // Auto-detect key type from content
        if (content.includes('BEGIN RSA PRIVATE KEY')) {
          updatedConfig.key_type = SSHKeyType.RSA
        } else if (content.includes('BEGIN OPENSSH PRIVATE KEY')) {
          updatedConfig.key_type = SSHKeyType.ED25519
        } else if (content.includes('BEGIN EC PRIVATE KEY')) {
          updatedConfig.key_type = SSHKeyType.ECDSA
        }
        
        // 한번에 모든 변경사항 적용
        if (onChange && typeof onChange === 'function') {
          onChange(updatedConfig)
        }
        
        // local state도 sync
        setKeyContent(content)
      }
      reader.readAsText(file)
    }
  }

  const testTunnel = async () => {
    if (!onTest) return
    
    setTestStatus({ status: 'testing' })
    
    try {
      // keyContent가 있으면 config에 업데이트해서 전송
      const configToTest = {
        ...config,
        private_key_content: keyContent || config.private_key_content
      }
      const result = await onTest(configToTest)
      
      if (result.success) {
        setTestStatus({ 
          status: 'connected', 
          message: 'SSH tunnel connected successfully!',
          result 
        })
        toast.success('SSH tunnel test successful!')
      } else {
        setTestStatus({ 
          status: 'failed', 
          message: result.errors.join(', ') || 'Connection failed',
          result
        })
        toast.error('SSH tunnel test failed')
      }
    } catch (error) {
      setTestStatus({ 
        status: 'failed', 
        message: error instanceof Error ? error.message : 'Unknown error'
      })
      toast.error(`SSH tunnel test failed: ${error}`)
    }
  }

  const getStatusIcon = () => {
    switch (testStatus.status) {
      case 'testing':
        return <TestTube className="h-4 w-4 animate-pulse text-blue-500" />
      case 'connected':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />
      default:
        return <Shield className="h-4 w-4" />
    }
  }

  const getStatusColor = () => {
    switch (testStatus.status) {
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

  const isConfigValid = () => {
    // 기본 필드 체크
    if (!config.ssh_host || !config.ssh_user) return false
    
    // Private Key 인증의 경우 키가 있는지 체크
    if (config.auth_method === SSHAuthMethod.PRIVATE_KEY) {
      // parent config에서 확인 - local state보다 더 안정적
      const hasPrivateKey = !!(config.private_key_content || config.private_key_path)
      return hasPrivateKey
    }
    
    // Password 인증의 경우 패스워드 체크
    if (config.auth_method === SSHAuthMethod.PASSWORD) {
      return !!config.ssh_password
    }
    
    // SSH Agent는 추가 설정 불필요
    if (config.auth_method === SSHAuthMethod.SSH_AGENT) {
      return true
    }
    
    return false
  }

  // Debug validation for troubleshooting
  const debugValidation = () => {
    if (typeof window !== 'undefined' && window.console) {
      console.log('🔍 SSH Config Validation Debug:', {
        ssh_host: config.ssh_host,
        ssh_user: config.ssh_user,
        auth_method: config.auth_method,
        private_key_content: config.private_key_content ? `[${config.private_key_content.length} chars]` : 'empty',
        private_key_path: config.private_key_path || 'empty',
        ssh_password: config.ssh_password ? '[PROVIDED]' : 'empty',
        enabled: config.enabled,
        isValid: isConfigValid(),
        // 추가 디버그 정보
        keyContent_local: keyContent ? `[${keyContent.length} chars]` : 'empty',
        keyContent_raw: keyContent?.substring(0, 100) + '...',
        merged_key: (keyContent || config.private_key_content) ? 'HAS_KEY' : 'NO_KEY'
      })
    }
  }

  // Enhanced debug validation with detailed step-by-step validation
  const getDetailedValidation = () => {
    const validationResults = {
      step1_ssh_host: !!config.ssh_host,
      step2_ssh_user: !!config.ssh_user,
      step3_auth_method: !!config.auth_method,
      step4_private_key: config.auth_method === SSHAuthMethod.PRIVATE_KEY 
        ? !!(config.private_key_content || keyContent || config.private_key_path) 
        : 'N/A',
      step5_password: config.auth_method === SSHAuthMethod.PASSWORD 
        ? !!config.ssh_password 
        : 'N/A',
      step6_ssh_agent: config.auth_method === SSHAuthMethod.SSH_AGENT ? true : 'N/A',
      final_validation: isConfigValid(),
      button_disabled_reasons: {
        testing: testStatus.status === 'testing',
        not_valid: !isConfigValid(),
        disabled_prop: disabled,
        no_onTest: !onTest
      }
    }
    return validationResults
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
              onChange={(e) => handleConfigChange('enabled', e.target.checked)}
              disabled={disabled}
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

      <CardContent className="space-y-6">
        {!config.enabled && (
          <Alert className="mb-4">
            <Info className="h-4 w-4" />
            <AlertDescription>
              SSH tunnel is disabled. Configure settings below and test the connection, then enable it to use for database connections.
            </AlertDescription>
          </Alert>
        )}
          {/* SSH Server Configuration */}
          <div className="space-y-4">
            <h3 className="text-md font-semibold flex items-center">
              <Server className="h-4 w-4 mr-2" />
              SSH Server Details
            </h3>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="md:col-span-2">
                <Label htmlFor="ssh-host">SSH Host <span className="text-red-500">*</span></Label>
                <Input
                  id="ssh-host"
                  placeholder="jump-server.example.com"
                  value={config.ssh_host}
                  onChange={(e) => handleConfigChange('ssh_host', e.target.value)}
                  disabled={disabled}
                  required
                />
              </div>
              
              <div>
                <Label htmlFor="ssh-port">SSH Port</Label>
                <Input
                  id="ssh-port"
                  type="number"
                  min="1"
                  max="65535"
                  placeholder="22"
                  value={config.ssh_port}
                  onChange={(e) => handleConfigChange('ssh_port', parseInt(e.target.value) || 22)}
                  disabled={disabled}
                />
              </div>
            </div>

            <div>
              <Label htmlFor="ssh-user">SSH Username <span className="text-red-500">*</span></Label>
              <Input
                id="ssh-user"
                placeholder="ubuntu"
                value={config.ssh_user}
                onChange={(e) => handleConfigChange('ssh_user', e.target.value)}
                disabled={disabled}
                required
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
                <TabsTrigger value={SSHAuthMethod.PRIVATE_KEY} disabled={disabled}>
                  Private Key
                </TabsTrigger>
                <TabsTrigger value={SSHAuthMethod.PASSWORD} disabled={disabled}>
                  Password
                </TabsTrigger>
                <TabsTrigger value={SSHAuthMethod.SSH_AGENT} disabled={disabled}>
                  SSH Agent
                </TabsTrigger>
              </TabsList>

              <TabsContent value={SSHAuthMethod.PRIVATE_KEY} className="space-y-4">
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="key-file">Private Key File</Label>
                    <div className="flex space-x-2">
                      <Input
                        ref={fileInputRef}
                        type="file"
                        onChange={handleFileUpload}
                        className="file:mr-4 file:py-1 file:px-4 file:rounded-md file:border-0 file:text-sm file:bg-primary file:text-primary-foreground"
                        disabled={disabled}
                      />
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      Upload your SSH private key file (any format: .pem, .key, id_rsa, etc.)
                    </p>
                  </div>

                  {config.private_key_path && (
                    <div>
                      <Label>Selected Key File</Label>
                      <div className="flex items-center space-x-2 p-2 border rounded">
                        <Key className="h-4 w-4" />
                        <span className="text-sm">{config.private_key_path}</span>
                        {config.key_type && (
                          <Badge variant="outline">{config.key_type.toUpperCase()}</Badge>
                        )}
                      </div>
                    </div>
                  )}

                  <div>
                    <Label htmlFor="key-passphrase">Private Key Passphrase (Optional)</Label>
                    <Input
                      id="key-passphrase"
                      type="password"
                      placeholder="Enter passphrase if key is encrypted"
                      value={config.private_key_passphrase || ''}
                      onChange={(e) => handleConfigChange('private_key_passphrase', e.target.value)}
                      disabled={disabled}
                    />
                  </div>

                  <div>
                    <Label htmlFor="key-content">Or paste private key content</Label>
                    <Textarea
                      id="key-content"
                      placeholder="-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC..."
                      value={keyContent}
                      onChange={(e) => {
                        const content = e.target.value
                        // parent config를 먼저 업데이트
                        handleConfigChange('private_key_content', content)
                        // local state sync
                        setKeyContent(content)
                      }}
                      rows={6}
                      className="font-mono text-sm"
                      disabled={disabled}
                    />
                  </div>
                </div>
              </TabsContent>

              <TabsContent value={SSHAuthMethod.PASSWORD} className="space-y-4">
                <div>
                  <Label htmlFor="ssh-password">SSH Password <span className="text-red-500">*</span></Label>
                  <Input
                    id="ssh-password"
                    type="password"
                    placeholder="Enter SSH password"
                    value={config.ssh_password || ''}
                    onChange={(e) => handleConfigChange('ssh_password', e.target.value)}
                    disabled={disabled}
                    required
                  />
                  <Alert className="mt-2">
                    <AlertTriangle className="h-4 w-4" />
                    <AlertDescription>
                      Password authentication is less secure. Consider using SSH keys instead.
                    </AlertDescription>
                  </Alert>
                </div>
              </TabsContent>

              <TabsContent value={SSHAuthMethod.SSH_AGENT} className="space-y-4">
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
                  min="1024"
                  max="65535"
                  placeholder="Auto-assign"
                  value={config.local_bind_port || ''}
                  onChange={(e) => handleConfigChange('local_bind_port', e.target.value ? parseInt(e.target.value) : undefined)}
                  disabled={disabled}
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
                  disabled={disabled}
                />
              </div>

              <div>
                <Label htmlFor="remote-port">Remote Port</Label>
                <Input
                  id="remote-port"
                  type="number"
                  min="1"
                  max="65535"
                  placeholder="3306"
                  value={config.remote_bind_port}
                  onChange={(e) => handleConfigChange('remote_bind_port', parseInt(e.target.value) || 3306)}
                  disabled={disabled}
                />
              </div>
            </div>
          </div>

          {/* Advanced Settings */}
          <Collapsible open={showAdvanced} onOpenChange={setShowAdvanced}>
            <CollapsibleTrigger className="flex items-center justify-between w-full p-0 border-0 bg-transparent hover:bg-transparent">
              <h3 className="text-md font-semibold">Advanced Settings</h3>
              <div className="p-2">
                {showAdvanced ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
              </div>
            </CollapsibleTrigger>

            <CollapsibleContent className="space-y-4 pt-4">
              <div className="p-4 border rounded-lg bg-muted/20 space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="connect-timeout">Connection Timeout (seconds)</Label>
                    <Input
                      id="connect-timeout"
                      type="number"
                      min="5"
                      max="60"
                      value={config.connect_timeout}
                      onChange={(e) => handleConfigChange('connect_timeout', parseInt(e.target.value) || 10)}
                      disabled={disabled}
                    />
                  </div>

                  <div>
                    <Label htmlFor="keepalive-interval">Keepalive Interval (seconds)</Label>
                    <Input
                      id="keepalive-interval"
                      type="number"
                      min="10"
                      max="300"
                      value={config.keepalive_interval}
                      onChange={(e) => handleConfigChange('keepalive_interval', parseInt(e.target.value) || 30)}
                      disabled={disabled}
                    />
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-4">
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="compression"
                      checked={config.compression}
                      onChange={(e) => handleConfigChange('compression', e.target.checked)}
                      disabled={disabled}
                    />
                    <Label htmlFor="compression">Enable Compression</Label>
                  </div>

                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="host-key-checking"
                      checked={config.strict_host_key_checking}
                      onChange={(e) => handleConfigChange('strict_host_key_checking', e.target.checked)}
                      disabled={disabled}
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
                    disabled={disabled}
                  />
                </div>
              </div>
            </CollapsibleContent>
          </Collapsible>

          {/* Test Results */}
          {testStatus.result && (
            <div className="space-y-3">
              <h3 className="text-md font-semibold">Test Results</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Card className="p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">SSH Connection</span>
                    {testStatus.result.ssh_connection_success ? (
                      <CheckCircle className="h-4 w-4 text-green-500" />
                    ) : (
                      <XCircle className="h-4 w-4 text-red-500" />
                    )}
                  </div>
                  {testStatus.result.ssh_connection_time_ms && (
                    <div className="text-xs text-muted-foreground">
                      Time: {testStatus.result.ssh_connection_time_ms.toFixed(2)}ms
                    </div>
                  )}
                </Card>

                <Card className="p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">Database Port</span>
                    {testStatus.result.database_connection_success ? (
                      <CheckCircle className="h-4 w-4 text-green-500" />
                    ) : (
                      <XCircle className="h-4 w-4 text-red-500" />
                    )}
                  </div>
                  {testStatus.result.database_connection_time_ms && (
                    <div className="text-xs text-muted-foreground">
                      Time: {testStatus.result.database_connection_time_ms.toFixed(2)}ms
                    </div>
                  )}
                </Card>
              </div>

              {testStatus.result.errors.length > 0 && (
                <Alert>
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>
                    <div className="space-y-1">
                      {testStatus.result.errors.map((error, index) => (
                        <div key={index} className="text-sm">{error}</div>
                      ))}
                    </div>
                  </AlertDescription>
                </Alert>
              )}

              {testStatus.result.warnings.length > 0 && (
                <Alert>
                  <Info className="h-4 w-4" />
                  <AlertDescription>
                    <div className="space-y-1">
                      {testStatus.result.warnings.map((warning, index) => (
                        <div key={index} className="text-sm">{warning}</div>
                      ))}
                    </div>
                  </AlertDescription>
                </Alert>
              )}
            </div>
          )}

          {/* Debug Panel - Show validation status in DEV mode */}
          {process.env.NODE_ENV === 'development' && (
            <div className="mt-6 p-4 border rounded-lg bg-yellow-50 dark:bg-yellow-900/20">
              <h4 className="text-sm font-semibold mb-3 flex items-center">
                🔍 Debug: Validation Status
              </h4>
              {(() => {
                const validation = getDetailedValidation()
                return (
                  <div className="space-y-2">
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className={`p-2 rounded ${validation.step1_ssh_host ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                        SSH Host: {validation.step1_ssh_host ? '✅' : '❌'} ({config.ssh_host || 'empty'})
                      </div>
                      <div className={`p-2 rounded ${validation.step2_ssh_user ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                        SSH User: {validation.step2_ssh_user ? '✅' : '❌'} ({config.ssh_user || 'empty'})
                      </div>
                      <div className={`p-2 rounded ${validation.step3_auth_method ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                        Auth Method: {validation.step3_auth_method ? '✅' : '❌'} ({config.auth_method})
                      </div>
                      {config.auth_method === SSHAuthMethod.PRIVATE_KEY && (
                        <div className={`p-2 rounded ${validation.step4_private_key ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                          Private Key: {validation.step4_private_key ? '✅' : '❌'} 
                          ({config.private_key_content ? 'content' : keyContent ? 'local' : config.private_key_path ? 'path' : 'none'})
                        </div>
                      )}
                      {config.auth_method === SSHAuthMethod.PASSWORD && (
                        <div className={`p-2 rounded ${validation.step5_password ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                          Password: {validation.step5_password ? '✅' : '❌'}
                        </div>
                      )}
                      {config.auth_method === SSHAuthMethod.SSH_AGENT && (
                        <div className="p-2 rounded bg-green-100 text-green-800">
                          SSH Agent: ✅ (No extra config needed)
                        </div>
                      )}
                    </div>
                    
                    <div className="mt-3 pt-3 border-t">
                      <div className={`p-2 rounded font-medium ${validation.final_validation ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                        Final Validation: {validation.final_validation ? '✅ VALID' : '❌ INVALID'}
                      </div>
                    </div>

                    <div className="mt-3 pt-3 border-t">
                      <h5 className="font-medium text-xs mb-2">Button Disabled Reasons:</h5>
                      <div className="space-y-1 text-xs">
                        <div className={validation.button_disabled_reasons.testing ? 'text-orange-600' : 'text-green-600'}>
                          Testing: {validation.button_disabled_reasons.testing ? '❌ In Progress' : '✅ Ready'}
                        </div>
                        <div className={validation.button_disabled_reasons.not_valid ? 'text-red-600' : 'text-green-600'}>
                          Validation: {validation.button_disabled_reasons.not_valid ? '❌ Invalid Config' : '✅ Valid Config'}
                        </div>
                        <div className={validation.button_disabled_reasons.disabled_prop ? 'text-orange-600' : 'text-green-600'}>
                          Disabled Prop: {validation.button_disabled_reasons.disabled_prop ? '❌ Component Disabled' : '✅ Enabled'}
                        </div>
                        <div className={validation.button_disabled_reasons.no_onTest ? 'text-red-600' : 'text-green-600'}>
                          Test Handler: {validation.button_disabled_reasons.no_onTest ? '❌ Missing onTest prop' : '✅ Handler Available'}
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })()}
            </div>
          )}

          {/* Test Connection */}
          <div className="flex justify-between items-center pt-4 border-t">
            <div className="space-y-1">
              {testStatus.message && (
                <p className={`text-sm ${
                  testStatus.status === 'connected' ? 'text-green-600' :
                  testStatus.status === 'failed' ? 'text-red-600' : 'text-gray-600'
                }`}>
                  {testStatus.message}
                </p>
              )}
              {testStatus.result && (
                <div className="text-xs text-muted-foreground">
                  Total test time: {testStatus.result.total_test_time_ms.toFixed(2)}ms
                  {testStatus.result.local_port && (
                    <> • Local port: {testStatus.result.local_port}</>
                  )}
                </div>
              )}
            </div>

            <Button
              onClick={() => {
                debugValidation()
                testTunnel()
              }}
              disabled={testStatus.status === 'testing' || !isConfigValid() || disabled || !onTest}
              variant={testStatus.status === 'connected' ? 'default' : 'outline'}
              className={
                testStatus.status === 'connected' ? 'bg-green-600 hover:bg-green-700' :
                testStatus.status === 'failed' ? 'border-red-500 text-red-500' : ''
              }
            >
              {testStatus.status === 'testing' ? (
                <>
                  <TestTube className="w-4 h-4 mr-2 animate-pulse" />
                  Testing...
                </>
              ) : testStatus.status === 'connected' ? (
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
    </Card>
  )
}
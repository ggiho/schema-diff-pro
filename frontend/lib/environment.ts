/**
 * Environment detection and configuration utilities
 * Handles both Docker and local development environments
 */

export type Environment = 'docker' | 'local' | 'production'

export interface EnvironmentConfig {
  apiBaseUrl: string
  wsBaseUrl: string
  isDevelopment: boolean
  isDocker: boolean
  environment: Environment
}

/**
 * Detect current runtime environment
 */
export function detectEnvironment(): Environment {
  // Check for explicit Docker environment flag
  if (process.env.DOCKER_ENV === 'true') {
    return 'docker'
  }
  
  // Check for Docker container indicators
  if (typeof window === 'undefined') {
    // Server-side checks
    if (process.env.NODE_ENV === 'production' && !process.env.VERCEL) {
      return 'docker'
    }
  }
  
  // Check for production environment
  if (process.env.NODE_ENV === 'production') {
    return 'production'
  }
  
  // Default to local development
  return 'local'
}

/**
 * Get API base URL based on environment
 */
export function getApiBaseUrl(): string {
  const env = detectEnvironment()
  
  // Check for explicit override
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL
  }
  
  switch (env) {
    case 'docker':
      return 'http://backend:8000'
    case 'production':
      return process.env.NEXT_PUBLIC_API_URL || 'https://api.yourdomain.com'
    case 'local':
    default:
      return 'http://localhost:8000'
  }
}

/**
 * Get WebSocket base URL based on environment
 */
export function getWsBaseUrl(): string {
  const apiUrl = getApiBaseUrl()
  return apiUrl.replace('http://', 'ws://').replace('https://', 'wss://')
}

/**
 * Get complete environment configuration
 */
export function getEnvironmentConfig(): EnvironmentConfig {
  const environment = detectEnvironment()
  const apiBaseUrl = getApiBaseUrl()
  const wsBaseUrl = getWsBaseUrl()
  
  return {
    apiBaseUrl,
    wsBaseUrl,
    isDevelopment: process.env.NODE_ENV !== 'production',
    isDocker: environment === 'docker',
    environment
  }
}

/**
 * Log environment information (for debugging)
 */
export function logEnvironmentInfo(): void {
  if (process.env.NODE_ENV === 'development') {
    const config = getEnvironmentConfig()
    console.log('🌍 Environment Configuration:', {
      environment: config.environment,
      apiBaseUrl: config.apiBaseUrl,
      wsBaseUrl: config.wsBaseUrl,
      isDevelopment: config.isDevelopment,
      isDocker: config.isDocker,
      nodeEnv: process.env.NODE_ENV,
      dockerEnv: process.env.DOCKER_ENV,
      nextPublicApiUrl: process.env.NEXT_PUBLIC_API_URL
    })
  }
}

// Client-side environment detection
export function getClientEnvironment(): 'browser' | 'server' {
  return typeof window !== 'undefined' ? 'browser' : 'server'
}

// Check if running in development mode
export function isDevelopment(): boolean {
  return process.env.NODE_ENV === 'development'
}

// Check if running in Docker
export function isDockerEnvironment(): boolean {
  return detectEnvironment() === 'docker'
}
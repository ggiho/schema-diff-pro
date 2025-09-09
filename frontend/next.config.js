const fs = require('fs')

/**
 * Detect runtime environment for Next.js configuration
 */
function detectEnvironment() {
  // Check for explicit Docker environment flag
  if (process.env.DOCKER_ENV === 'true') {
    return 'docker'
  }
  
  // Check for Docker container indicators
  if (fs.existsSync('/.dockerenv')) {
    return 'docker'
  }
  
  // Check for production environment
  if (process.env.NODE_ENV === 'production' && !process.env.VERCEL) {
    return 'docker' // Assume Docker in production unless on Vercel
  }
  
  return 'local'
}

/**
 * Get API base URL based on environment
 */
function getApiBaseUrl() {
  // Check for explicit override
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL
  }
  
  const env = detectEnvironment()
  
  switch (env) {
    case 'docker':
      return 'http://backend:8000'
    default:
      return 'http://localhost:8000'
  }
}

// Get the appropriate API base URL
const apiBaseUrl = getApiBaseUrl()

// Log configuration for debugging
console.log('🚀 Next.js Configuration:', {
  environment: detectEnvironment(),
  apiBaseUrl,
  nodeEnv: process.env.NODE_ENV,
  dockerEnv: process.env.DOCKER_ENV,
  nextPublicApiUrl: process.env.NEXT_PUBLIC_API_URL
})

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  
  // Environment-specific configuration
  env: {
    API_BASE_URL: apiBaseUrl,
    ENVIRONMENT: detectEnvironment(),
  },
  
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${apiBaseUrl}/api/:path*`,
      },
      // Note: WebSocket connections should be handled directly from client
      // WebSocket rewrites are not supported by Next.js
    ]
  },
  
  // Optimize for Docker builds
  output: detectEnvironment() === 'docker' ? 'standalone' : undefined,
}

module.exports = nextConfig
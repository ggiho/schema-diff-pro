import axios from 'axios'
import { DatabaseConfig, ComparisonOptions, ComparisonResult, SyncScript } from '@/types'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export async function startComparison(
  sourceConfig: DatabaseConfig,
  targetConfig: DatabaseConfig,
  options?: ComparisonOptions
) {
  const response = await api.post('/comparison/compare', {
    source_config: sourceConfig,
    target_config: targetConfig,
    options: options,
  })
  return response.data
}

export async function getComparisonResult(comparisonId: string): Promise<ComparisonResult> {
  const response = await api.get(`/comparison/${comparisonId}/result`)
  return response.data
}

export async function getComparisonStatus(comparisonId: string) {
  const response = await api.get(`/comparison/${comparisonId}/status`)
  return response.data
}

export async function generateSyncScript(comparisonId: string): Promise<SyncScript> {
  const response = await api.post(`/sync/${comparisonId}/generate`)
  return response.data
}

export async function previewSyncChanges(comparisonId: string) {
  const response = await api.get(`/sync/${comparisonId}/preview`)
  return response.data
}

export async function validateSyncScript(comparisonId: string) {
  const response = await api.post(`/sync/${comparisonId}/validate`)
  return response.data
}

// Profile management
export async function createProfile(profile: any) {
  const response = await api.post('/profiles/', profile)
  return response.data
}

export async function listProfiles() {
  const response = await api.get('/profiles/')
  return response.data
}

export async function getProfile(profileId: string) {
  const response = await api.get(`/profiles/${profileId}`)
  return response.data
}

export async function updateProfile(profileId: string, profile: any) {
  const response = await api.put(`/profiles/${profileId}`, profile)
  return response.data
}

export async function deleteProfile(profileId: string) {
  const response = await api.delete(`/profiles/${profileId}`)
  return response.data
}

export async function runProfile(profileId: string) {
  const response = await api.post(`/profiles/${profileId}/run`)
  return response.data
}

// Recent comparisons
export async function getRecentComparisons(limit: number = 10) {
  const response = await api.get(`/comparison/recent/list?limit=${limit}`)
  return response.data
}
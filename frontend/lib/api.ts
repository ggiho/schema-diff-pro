import axios from 'axios'
import { 
  DatabaseConfig, 
  DatabaseConfigWithSSH,
  ComparisonOptions, 
  ComparisonResult, 
  SyncScript,
  SyncDirection,
  ComparisonProfile,
  ComparisonStartResponse,
  ComparisonStatus,
  SyncPreview,
  SyncValidationResult,
  RecentComparison,
} from '@/types'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export async function startComparison(
  sourceConfig: DatabaseConfig | DatabaseConfigWithSSH,
  targetConfig: DatabaseConfig | DatabaseConfigWithSSH,
  options?: ComparisonOptions
): Promise<ComparisonStartResponse> {
  const response = await api.post<ComparisonStartResponse>('/comparison/compare', {
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

export async function rerunComparison(comparisonId: string): Promise<ComparisonStartResponse> {
  const response = await api.post<ComparisonStartResponse>(`/comparison/${comparisonId}/rerun`)
  return response.data
}

export async function getComparisonStatus(comparisonId: string): Promise<ComparisonStatus> {
  const response = await api.get<ComparisonStatus>(`/comparison/${comparisonId}/status`)
  return response.data
}

export interface SyncScriptFilters {
  schemas?: string[]
  object_types?: string[]
  severities?: string[]
}

export async function generateSyncScript(
  comparisonId: string,
  direction?: SyncDirection,
  filters?: SyncScriptFilters
): Promise<SyncScript> {
  const response = await api.post<SyncScript>(
    `/sync/${comparisonId}/generate`,
    {
      direction: direction || SyncDirection.SOURCE_TO_TARGET,
      ...filters
    }
  )
  return response.data
}

export async function previewSyncChanges(comparisonId: string): Promise<SyncPreview> {
  const response = await api.get<SyncPreview>(`/sync/${comparisonId}/preview`)
  return response.data
}

export async function validateSyncScript(comparisonId: string): Promise<SyncValidationResult> {
  const response = await api.post<SyncValidationResult>(`/sync/${comparisonId}/validate`)
  return response.data
}

// Script execution
import { 
  ScriptAnalysisResponse, 
  ExecuteScriptRequest, 
  ExecuteScriptResponse 
} from '@/types'

export async function analyzeScript(
  comparisonId: string, 
  script: string, 
  targetDatabase: 'source' | 'target'
): Promise<ScriptAnalysisResponse> {
  const response = await api.post<ScriptAnalysisResponse>(
    `/sync/${comparisonId}/analyze`,
    { script, target_database: targetDatabase }
  )
  return response.data
}

export async function executeScript(
  comparisonId: string,
  script: string,
  targetDatabase: 'source' | 'target'
): Promise<ExecuteScriptResponse> {
  const response = await api.post<ExecuteScriptResponse>(
    `/sync/${comparisonId}/execute`,
    { script, target_database: targetDatabase }
  )
  return response.data
}

// Profile management
export async function createProfile(profile: Omit<ComparisonProfile, 'id' | 'created_at'>): Promise<ComparisonProfile> {
  const response = await api.post<ComparisonProfile>('/profiles/', profile)
  return response.data
}

export async function listProfiles(): Promise<ComparisonProfile[]> {
  const response = await api.get<ComparisonProfile[]>('/profiles/')
  return response.data
}

export async function getProfile(profileId: string): Promise<ComparisonProfile> {
  const response = await api.get<ComparisonProfile>(`/profiles/${profileId}`)
  return response.data
}

export async function updateProfile(
  profileId: string, 
  profile: Partial<Omit<ComparisonProfile, 'id' | 'created_at'>>
): Promise<ComparisonProfile> {
  const response = await api.put<ComparisonProfile>(`/profiles/${profileId}`, profile)
  return response.data
}

export async function deleteProfile(profileId: string): Promise<{ success: boolean }> {
  const response = await api.delete<{ success: boolean }>(`/profiles/${profileId}`)
  return response.data
}

export async function runProfile(profileId: string): Promise<ComparisonStartResponse> {
  const response = await api.post<ComparisonStartResponse>(`/profiles/${profileId}/run`)
  return response.data
}

// Recent comparisons
export async function getRecentComparisons(limit: number = 10): Promise<RecentComparison[]> {
  const response = await api.get<RecentComparison[]>(`/comparison/recent/list?limit=${limit}`)
  return response.data
}

// Re-export types for convenience
export type { 
  ComparisonProfile, 
  ComparisonStartResponse, 
  ComparisonStatus,
  RecentComparison,
} from '@/types'
import { create } from 'zustand'
import { DatabaseConfig, ComparisonOptions } from '@/types'

interface ComparisonStore {
  sourceConfig: DatabaseConfig | null
  targetConfig: DatabaseConfig | null
  comparisonOptions: ComparisonOptions
  setSourceConfig: (config: DatabaseConfig | null) => void
  setTargetConfig: (config: DatabaseConfig | null) => void
  setComparisonOptions: (options: ComparisonOptions) => void
}

export const useComparisonStore = create<ComparisonStore>((set) => ({
  sourceConfig: null,
  targetConfig: null,
  comparisonOptions: {
    compare_tables: true,
    compare_columns: true,
    compare_indexes: true,
    compare_constraints: true,
    compare_procedures: true,
    compare_functions: true,
    compare_views: true,
    compare_triggers: true,
    compare_events: false,
    ignore_auto_increment: true,
    ignore_comments: false,
    ignore_charset: false,
    ignore_collation: false,
    case_sensitive: true,
  },
  setSourceConfig: (config) => set({ sourceConfig: config }),
  setTargetConfig: (config) => set({ targetConfig: config }),
  setComparisonOptions: (options) => set({ comparisonOptions: options }),
}))
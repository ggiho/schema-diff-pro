import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { 
  DatabaseConfig, 
  DatabaseConfigWithSSH, 
  ComparisonOptions, 
  ComparisonResult 
} from '@/types'

type DatabaseConfiguration = DatabaseConfig | DatabaseConfigWithSSH

interface ComparisonStore {
  sourceConfig: DatabaseConfiguration | null
  targetConfig: DatabaseConfiguration | null
  comparisonOptions: ComparisonOptions
  currentComparisonId: string | null
  currentComparisonResult: ComparisonResult | null
  setSourceConfig: (config: DatabaseConfiguration | null) => void
  setTargetConfig: (config: DatabaseConfiguration | null) => void
  setComparisonOptions: (options: ComparisonOptions) => void
  setCurrentComparison: (id: string | null, result: ComparisonResult | null) => void
  clearComparison: () => void
}

export const useComparisonStore = create<ComparisonStore>()(
  persist(
    (set) => ({
      sourceConfig: null,
      targetConfig: null,
      currentComparisonId: null,
      currentComparisonResult: null,
      comparisonOptions: {
        compare_tables: true,
        compare_columns: true,
        compare_indexes: true,
        compare_constraints: true,
        compare_procedures: false,
        compare_functions: false,
        compare_views: false,
        compare_triggers: false,
        compare_events: false,
        compare_partitions: false,
        ignore_auto_increment: true,
        ignore_comments: false,
        ignore_charset: false,
        ignore_collation: false,
        case_sensitive: true,
      },
      setSourceConfig: (config) => set({ sourceConfig: config }),
      setTargetConfig: (config) => set({ targetConfig: config }),
      setComparisonOptions: (options) => set({ comparisonOptions: options }),
      setCurrentComparison: (id, result) => set({ 
        currentComparisonId: id, 
        currentComparisonResult: result 
      }),
      clearComparison: () => set({ 
        currentComparisonId: null, 
        currentComparisonResult: null 
      }),
    }),
    {
      name: 'schema-diff-storage',
      partialize: (state) => ({
        sourceConfig: state.sourceConfig,
        targetConfig: state.targetConfig,
        comparisonOptions: state.comparisonOptions,
        currentComparisonId: state.currentComparisonId,
        currentComparisonResult: state.currentComparisonResult,
      }),
    }
  )
)
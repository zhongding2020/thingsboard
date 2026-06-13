import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'

export interface AnalysisFilter {
  timeRange: [string, string] | null
  deviceId: string
  featureFields: string[]
  targetFields: string[]
}

export interface ProfilingEntry {
  field: string
  dtype: string
  count: number
  missing_count: number
  missing_rate: number
  mean: number | null
  std: number | null
  min: number | null
  max: number | null
  iqr_outliers: number
}

export interface CorrelationResult {
  x: number[]
  y: number[]
  value: number[]
}

export interface RegressionResult {
  predicted: number[]
  actual: number[]
}

export interface RecommendationResult {
  recommended_parameters: Record<string, number>
  predicted_target: number
  alternatives: Record<string, number>[]
  important_features: string[]
  risk_notes: string[]
  model_metrics: Record<string, unknown>
  dataset_summary: Record<string, unknown>
  can_submit_as_proposed: boolean
}

export const useAnalysisStore = defineStore('analysis', () => {
  const filter = reactive<AnalysisFilter>({
    timeRange: null,
    deviceId: '',
    featureFields: [],
    targetFields: [],
  })

  const profileResult = ref<Record<string, Record<string, unknown>>>({})
  const correlationResult = ref<CorrelationResult | null>(null)
  const regressionResult = ref<RegressionResult | null>(null)
  const recommendationResult = ref<RecommendationResult | null>(null)

  function setFilter(partial: Partial<AnalysisFilter>) {
    Object.assign(filter, partial)
  }

  return { filter, profileResult, correlationResult, regressionResult, recommendationResult, setFilter }
})

import client from './client'

export interface ProfileRequest {
  feature_fields: string[]
  target_fields: string[]
  missing_strategy?: string
  max_samples?: number | null
}

export interface CorrelationRequest {
  field_x: string
  field_y: string
  method?: string
}

export interface RegressionRequest {
  feature_fields: string[]
  target_field: string
  model_type?: string
}

export interface RecommendationRequest {
  feature_fields: string[]
  target_field: string
  target_value: number
  constraints?: { field: string; min?: number; max?: number }[]
}

export function profile(data: ProfileRequest): Promise<unknown> {
  return client.post('/analysis/profile', data).then((res) => res.data)
}

export function correlation(data: CorrelationRequest): Promise<unknown> {
  return client.post('/analysis/correlation', data).then((res) => res.data)
}

export function regression(data: RegressionRequest): Promise<unknown> {
  return client.post('/analysis/regression', data).then((res) => res.data)
}

export function recommendation(data: RecommendationRequest): Promise<unknown> {
  return client.post('/analysis/recommendation', data).then((res) => res.data)
}

export function submitRecommendation(data?: Record<string, unknown>): Promise<unknown> {
  return client.post('/analysis/recommendation/submit', data).then((res) => res.data)
}

export function uploadExcel(file: File): Promise<{ dataset_id: string; fields: { features: string[]; targets: string[] }; sample_count: number }> {
  const form = new FormData()
  form.append('file', file)
  return client.post('/analysis/excel/upload', form).then((res) => res.data)
}

export function excelProfile(datasetId: string): Promise<unknown> {
  return client.post('/analysis/excel/profile', { dataset_id: datasetId }).then((res) => res.data)
}

export function excelCorrelation(datasetId: string, data: { field_x: string; field_y: string; method?: string }): Promise<unknown> {
  return client.post('/analysis/excel/correlation', { dataset_id: datasetId, ...data }).then((res) => res.data)
}

export function excelRegression(datasetId: string, data: { feature_fields: string[]; target_field: string; model_type?: string }): Promise<unknown> {
  return client.post('/analysis/excel/regression', { dataset_id: datasetId, ...data }).then((res) => res.data)
}

export function excelRecommendation(datasetId: string, data: Record<string, unknown>): Promise<unknown> {
  return client.post('/analysis/excel/recommendation', { dataset_id: datasetId, ...data }).then((res) => res.data)
}

import client from './client'

export interface DatasetFields {
  features: string[]
  targets: string[]
}

export interface DatasetResult {
  dataset_id: string
  fields: DatasetFields
  sample_count: number
}

export interface FieldMeta {
  name: string
  type: string
  min?: number
  max?: number
}

export interface PreviewResponse {
  rows: Record<string, unknown>[]
  total: number
  page: number
  size: number
  fields: {
    features: FieldMeta[]
    targets: FieldMeta[]
  }
}

export interface CorrelationRequest {
  dataset_id: string
  field_x?: string
  field_y?: string
  method?: string
}

export interface RegressionRequest {
  dataset_id: string
  feature_fields: string[]
  target_field: string
  model_type?: string
}

export interface RecommendationRequest {
  dataset_id: string
  feature_fields: string[]
  target_field: string
  target_value: number
  constraints?: { field: string; min?: number; max?: number }[]
}

export function queryDataset(deviceId: string, since?: string): Promise<DatasetResult> {
  return client.post('/analysis/dataset/query', { device_id: deviceId, since }).then((res) => res.data)
}

export function uploadDataset(file: File): Promise<DatasetResult> {
  const form = new FormData()
  form.append('file', file)
  return client.post('/analysis/dataset/upload', form).then((res) => res.data)
}

export function previewDataset(id: string, page = 1, size = 50): Promise<PreviewResponse> {
  return client.get(`/analysis/dataset/${id}/preview`, { params: { page, size } }).then((res) => res.data)
}

export function profile(datasetId: string): Promise<unknown> {
  return client.post('/analysis/profile', { dataset_id: datasetId }).then((res) => res.data)
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

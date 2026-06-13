import client from './client'

export interface RecordsQuery {
  barcode?: string
  device_id?: string
  start_time?: string
  end_time?: string
  page?: number
  page_size?: number
}

export interface AnalysisRecord {
  barcode: string
  device_id: string
  processed_at: string
  params: Record<string, number | string>
  station_id: string | null
  inspected_at: string | null
  results: Record<string, string | number> | null
}

export interface RecordsResponse {
  items: AnalysisRecord[]
  total: number
  page: number
  page_size: number
}

export function queryRecords(params: RecordsQuery): Promise<RecordsResponse> {
  return client.get('/analysis/records', { params }).then((res) => res.data)
}

export function listDevices(): Promise<string[]> {
  return client.get('/analysis/devices').then((res) => res.data)
}

import client from './client'

export interface DashboardStats {
  today_data_count: number
  total_records: number
  device_count: number
  pending_approvals: number
  latest_records: { barcode: string; device_id: string; processed_at: string }[]
}

export function fetchStats(): Promise<DashboardStats> {
  return client.get('/analysis/stats').then((res) => res.data)
}

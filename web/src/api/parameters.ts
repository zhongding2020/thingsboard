import client from './client'

export interface ParameterItem {
  id: number
  set_id: number
  param_key: string
  param_value: unknown
  unit: string | null
  data_type: string
  min_value: number | null
  max_value: number | null
  description: string | null
}

export interface ParameterSet {
  id: number
  name: string
  device_type: string
  version: number
  status: string
  source: string
  created_by: string
  approved_by: string | null
  activated_by: string | null
  note: string | null
  created_at: string
  updated_at: string
  approved_at: string | null
  activated_at: string | null
  archived_at: string | null
}

export interface ParameterSetWithItems {
  parameter_set: ParameterSet
  items: ParameterItem[]
  checksum: string
}

export function listSets(): Promise<ParameterSet[]> {
  return client.get('/parameters/sets').then((res) => res.data)
}

export function getSet(id: number): Promise<ParameterSetWithItems> {
  return client.get(`/parameters/sets/${id}`).then((res) => res.data)
}

export function createSet(data?: Record<string, unknown>): Promise<ParameterSet> {
  return client.post('/parameters/sets', data).then((res) => res.data)
}

export function submitSet(id: number, data: { actor: string; note?: string }): Promise<ParameterSet> {
  return client.post(`/parameters/sets/${id}/submit`, data).then((res) => res.data)
}

export function approveSet(id: number, data: { actor: string; note?: string }): Promise<ParameterSet> {
  return client.post(`/parameters/sets/${id}/approve`, data).then((res) => res.data)
}

export function rejectSet(id: number, data: { actor: string; note?: string }): Promise<ParameterSet> {
  return client.post(`/parameters/sets/${id}/reject`, data).then((res) => res.data)
}

export function activateSet(id: number, data: { actor: string; note?: string }): Promise<ParameterSet> {
  return client.post(`/parameters/sets/${id}/activate`, data).then((res) => res.data)
}

export function getLatest(deviceType: string): Promise<ParameterSetWithItems> {
  return client.get('/parameters/latest', { params: { device_type: deviceType } }).then((res) => res.data)
}

export function recordConfirmation(data: {
  device_id: string
  device_type: string
  parameter_set_id: number
  parameter_version: number
  status: string
  message?: string
}): Promise<void> {
  return client.post('/parameters/confirmations', data).then((res) => res.data)
}

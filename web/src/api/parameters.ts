import client from './client'

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

export function listSets(): Promise<ParameterSet[]> {
  return client.get('/parameters/sets').then((res) => res.data)
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

export function getLatest(deviceType: string): Promise<unknown> {
  return client.get('/parameters/latest', { params: { device_type: deviceType } }).then((res) => res.data)
}

export function recordConfirmation(data?: Record<string, unknown>): Promise<unknown> {
  return client.post('/parameters/confirmations', data).then((res) => res.data)
}

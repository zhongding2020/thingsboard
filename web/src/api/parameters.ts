import client from './client'

export function createSet(data?: Record<string, unknown>): Promise<unknown> {
  return client.post('/parameters/sets', data).then((res) => res.data)
}

export function submitSet(id: string): Promise<unknown> {
  return client.post(`/parameters/sets/${id}/submit`).then((res) => res.data)
}

export function approveSet(id: string): Promise<unknown> {
  return client.post(`/parameters/sets/${id}/approve`).then((res) => res.data)
}

export function rejectSet(id: string, data?: Record<string, unknown>): Promise<unknown> {
  return client.post(`/parameters/sets/${id}/reject`, data).then((res) => res.data)
}

export function activateSet(id: string): Promise<unknown> {
  return client.post(`/parameters/sets/${id}/activate`).then((res) => res.data)
}

export function getLatest(): Promise<unknown> {
  return client.get('/parameters/sets/latest').then((res) => res.data)
}

export function recordConfirmation(data?: Record<string, unknown>): Promise<unknown> {
  return client.post('/parameters/confirmations', data).then((res) => res.data)
}

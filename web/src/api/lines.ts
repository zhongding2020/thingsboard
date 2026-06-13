import client from './client'

export interface LineResponse {
  id: string
  name: string
  responsible: string
  location: string | null
  device_count: number
  created_at: string
  updated_at: string
}

export interface DeviceResponse {
  id: string
  line_id: string | null
  line_name: string | null
  name: string
  type: string
  icon: string | null
  description: string | null
}

export interface LineDetailResponse extends LineResponse {
  devices: DeviceResponse[]
}

export interface CreateLineRequest {
  name: string
  responsible: string
  location?: string
}

export interface UpdateLineRequest {
  name?: string
  responsible?: string
  location?: string
}

export interface UpdateDeviceRequest {
  name?: string
  type?: string
  icon?: string
  description?: string
  line_id?: string
}

export function listLines(): Promise<LineResponse[]> {
  return client.get('/lines').then((res) => res.data)
}

export function getLine(id: string): Promise<LineDetailResponse> {
  return client.get(`/lines/${id}`).then((res) => res.data)
}

export function createLine(data: CreateLineRequest): Promise<LineResponse> {
  return client.post('/lines', data).then((res) => res.data)
}

export function updateLine(id: string, data: UpdateLineRequest): Promise<LineResponse> {
  return client.put(`/lines/${id}`, data).then((res) => res.data)
}

export function deleteLine(id: string): Promise<void> {
  return client.delete(`/lines/${id}`)
}

export function listDevices(lineId?: string): Promise<DeviceResponse[]> {
  const params = lineId ? { line_id: lineId } : {}
  return client.get('/devices', { params }).then((res) => res.data)
}

export function getDevice(id: string): Promise<DeviceResponse> {
  return client.get(`/devices/${id}`).then((res) => res.data)
}

export function updateDevice(id: string, data: UpdateDeviceRequest): Promise<DeviceResponse> {
  return client.put(`/devices/${id}`, data).then((res) => res.data)
}

export function deleteDevice(id: string): Promise<void> {
  return client.delete(`/devices/${id}`)
}

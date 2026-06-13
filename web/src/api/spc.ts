import client from './client'

export interface SpcRequest {
  device_id: string
  field?: string
  usl?: number
  lsl?: number
  target?: number
  since?: string
}

export interface SpcResult {
  overview: ParamOverview[]
  i_chart: IChart | null
  mr_chart: MrChart | null
  histogram: Histogram | null
  capability: Capability | null
  p_chart: PChart | null
  summary: SummaryStats | null
}

export interface ParamOverview {
  field: string
  n: number
  mean: number
  std: number
  usl: number
  lsl: number
  cpk: number | null
  outlier_count: number
  status: 'normal' | 'marginal' | 'abnormal' | 'no_spec'
}

export interface IChart {
  values: number[]
  labels: string[]
  mean: number
  ucl: number
  lcl: number
  alerts: number[]
}

export interface MrChart {
  values: number[]
  labels: string[]
  mr_bar: number
  ucl: number
}

export interface Histogram {
  bins: number[]
  counts: number[]
  curve_x: number[]
  curve_y: number[]
}

export interface Capability {
  cp: number
  cpk: number
  pp: number
  ppk: number
  usl: number
  lsl: number
  target: number | null
}

export interface PChart {
  periods: string[]
  rates: number[]
  total_count: number
  defect_count: number
  ucl: number
  p_bar: number
}

export interface SummaryStats {
  n: number
  mean: number
  std: number
  min_val: number
  max_val: number
  normality_p: number | null
}

export function fetchSpc(data: SpcRequest): Promise<SpcResult> {
  return client.post('/analysis/spc', data).then((res) => res.data)
}

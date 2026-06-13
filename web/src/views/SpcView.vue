<template>
  <div class="spc-view" :style="app.fullscreen ? { height: '100vh', padding: '8px' } : {}">
    <!-- Line context breadcrumb (shown when viewing from line detail) -->
    <div v-if="route.query.line && route.query.device" class="spc-breadcrumb">
      <router-link to="/lines" class="bc-link">线体监控</router-link>
      <span class="bc-sep">›</span>
      <router-link :to="`/lines/${route.query.line}`" class="bc-link">{{ lineName || route.query.line }}</router-link>
      <span class="bc-sep">›</span>
      <span class="bc-current">{{ deviceInfo?.name || route.query.device }}</span>
      <el-button v-if="deviceInfo" text size="small" @click="editingDevice = true" style="margin-left:auto">编辑设备</el-button>
    </div>

    <div v-if="deviceInfo" class="device-info-bar">
      <span class="info-item"><span class="info-label">类型</span> {{ deviceLabel(deviceInfo.type) }}</span>
      <span v-if="deviceInfo.description" class="info-item"><span class="info-label">描述</span> {{ deviceInfo.description }}</span>
    </div>

    <div class="spc-header">
      <h2 class="page-title">设备监控</h2>
      <p class="page-desc">工艺参数SPC控制图</p>
    </div>

    <el-card class="spc-filter-card">
      <div class="spc-filter-bar">
        <el-form :inline="true" :model="filter">
          <el-form-item label="设备">
            <el-select v-model="filter.deviceId" placeholder="选择设备" clearable style="width: 160px" @change="handleDeviceChange">
              <el-option v-for="d in devices" :key="d" :label="d" :value="d" />
            </el-select>
          </el-form-item>
          <el-form-item label="时间范围">
            <el-date-picker
              v-model="timeRange"
              type="datetimerange"
              range-separator="至"
              start-placeholder="开始时间"
              end-placeholder="结束时间"
            />
          </el-form-item>
          <el-form-item label="USL">
            <el-input-number v-model="spec.usl" :precision="2" :step="0.1" placeholder="上限" size="small" controls-position="right" style="width: 120px" />
          </el-form-item>
          <el-form-item label="LSL">
            <el-input-number v-model="spec.lsl" :precision="2" :step="0.1" placeholder="下限" size="small" controls-position="right" style="width: 120px" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleQuery" :loading="loading">查询</el-button>
            <el-button text size="small" @click="spec.usl = undefined; spec.lsl = undefined" v-if="spec.usl !== undefined || spec.lsl !== undefined">清除规格</el-button>
          </el-form-item>
        </el-form>
        <div class="spc-monitor-controls">
          <div class="monitor-interval">
            <span>间隔</span>
            <el-select v-model="monitorInterval" size="small" style="width: 80px">
              <el-option label="5s" :value="5" />
              <el-option label="10s" :value="10" />
              <el-option label="30s" :value="30" />
            </el-select>
          </div>
          <el-button
            :type="monitoring ? 'danger' : 'success'"
            @click="toggleMonitoring"
            size="small"
          >
            {{ monitoring ? '● 停止监控' : '● 启动监控' }}
          </el-button>
          <el-button text @click="app.toggleFullscreen" class="fullscreen-btn">
            {{ app.fullscreen ? '退出全屏' : '全屏' }}
          </el-button>
        </div>
      </div>
      <div v-if="monitoring" class="monitor-bar">
        <span class="monitor-dot" /> 监控中 · 下次刷新 {{ countdown }}s · 数据点 {{ spcResult?.summary?.n ?? 0 }}
      </div>
    </el-card>

    <el-card v-if="spcResult?.overview?.length" class="overview-card">
      <template #header>
        <span class="section-title">参数概览</span>
        <span class="section-subtitle">点击行切换 SPC 图</span>
      </template>
      <el-table
        :data="spcResult.overview"
        stripe
        size="small"
        highlight-current-row
        @row-click="handleParamClick"
      >
        <el-table-column prop="field" label="参数" min-width="140" class-name="cell-mono" />
        <el-table-column prop="usl" label="上限(USL)" width="110" class-name="cell-mono" />
        <el-table-column prop="lsl" label="下限(LSL)" width="110" class-name="cell-mono" />
        <el-table-column prop="n" label="数据量" width="80" class-name="cell-mono" />
        <el-table-column label="Cpk" width="80" class-name="cell-mono">
          <template #default="{ row }">
            {{ row.cpk !== null ? row.cpk.toFixed(2) : '—' }}
          </template>
        </el-table-column>
        <el-table-column prop="outlier_count" label="离群数" width="80" class-name="cell-mono" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <div v-if="spcResult?.i_chart" class="spc-charts-grid" :style="app.fullscreen ? { flex: 1, minHeight: 0 } : {}">
      <el-card class="chart-card" v-for="chart in charts" :key="chart.title">
        <template #header>
          <span class="chart-title">{{ chart.title }}</span>
        </template>
        <div class="chart-body">
          <v-chart v-if="chart.visible" :option="chart.option" :style="{ width: '100%', height: chart.height + 'px' }" />
          <el-empty v-else description="暂无数据" :image-size="40" />
        </div>
      </el-card>
    </div>

    <el-dialog v-model="editingDevice" title="编辑设备" width="480px">
      <el-form :model="deviceForm" label-width="80px">
        <el-form-item label="名称"><el-input v-model="deviceForm.name" /></el-form-item>
        <el-form-item label="类型"><el-input v-model="deviceForm.type" /></el-form-item>
        <el-form-item label="图标"><el-input v-model="deviceForm.icon" placeholder="Element Plus icon name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="deviceForm.description" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editingDevice = false">取消</el-button>
        <el-button type="primary" @click="saveDeviceInfo" :loading="savingDevice">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch, watchEffect } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  MarkLineComponent,
  MarkPointComponent,
  GraphicComponent,
} from 'echarts/components'
import { fetchSpc, type SpcResult, type ParamOverview } from '@/api/spc'
import { listDevices } from '@/api/records'
import { useRoute } from 'vue-router'
import { getDevice, updateDevice, getLine, type DeviceResponse } from '@/api/lines'
import { deviceLabel } from '@/utils/device-icons'
import { useAppStore } from '@/stores/app'

use([
  CanvasRenderer, LineChart, BarChart,
  GridComponent, TooltipComponent, MarkLineComponent, MarkPointComponent, GraphicComponent,
])

const app = useAppStore()

const devices = ref<string[]>([])
const timeRange = ref<[Date, Date] | null>([new Date(Date.now() - 604800000), new Date()])
const spcResult = ref<SpcResult | null>(null)
const selectedField = ref('')
const loading = ref(false)

const monitoring = ref(false)
const monitorInterval = ref(10)
const countdown = ref(0)
let monitorTimer: ReturnType<typeof setInterval> | undefined
let countdownTimer: ReturnType<typeof setInterval> | undefined

const SAVED_DEVICE_KEY = 'spc-device-id'

const filter = reactive({
  deviceId: localStorage.getItem(SAVED_DEVICE_KEY) || '',
})

const spec = reactive<{ usl?: number; lsl?: number }>({})

const route = useRoute()
const deviceInfo = ref<DeviceResponse | null>(null)
const lineName = ref('')
const editingDevice = ref(false)
const savingDevice = ref(false)
const deviceForm = ref({ name: '', type: '', icon: '', description: '' })

const charts = computed(() => {
  const r = spcResult.value
  if (!r) return []
  return [
    {
      title: `I 单值图 — ${selectedField.value}`,
      height: 200,
      visible: !!r.i_chart,
      option: buildIChartOption(r.i_chart),
    },
    {
      title: 'MR 移动极差图',
      height: 200,
      visible: !!r.mr_chart,
      option: buildMrChartOption(r.mr_chart),
    },
    {
      title: '直方图 + 正态曲线',
      height: 200,
      visible: !!r.histogram,
      option: buildHistogramOption(r.histogram, r.capability),
    },
    {
      title: 'P 不合格品率图',
      height: 200,
      visible: !!(r.p_chart && r.p_chart.periods.length > 0),
      option: buildPChartOption(r.p_chart),
    },
    {
      title: '过程能力指数',
      height: 160,
      visible: !!r.capability,
      option: buildCapabilityOption(r.capability),
    },
    {
      title: '数据摘要',
      height: 160,
      visible: !!r.summary,
      option: buildSummaryOption(r.summary, r.capability),
    },
  ]
})

function statusTagType(status: string): string {
  switch (status) {
    case 'normal': return 'success'
    case 'marginal': return 'warning'
    case 'abnormal': return 'danger'
    case 'no_spec': return 'info'
    default: return 'info'
  }
}

function statusText(status: string): string {
  switch (status) {
    case 'normal': return '正常'
    case 'marginal': return '边缘'
    case 'abnormal': return '异常'
    case 'no_spec': return '无规格'
    default: return status
  }
}

function handleDeviceChange() {
  localStorage.setItem(SAVED_DEVICE_KEY, filter.deviceId)
}

function handleParamClick(row: ParamOverview) {
  selectedField.value = row.field
  loadSpc()
}

async function loadSpc() {
  if (!filter.deviceId || !selectedField.value) return
  loading.value = true
  try {
    spcResult.value = await fetchSpc({
      device_id: filter.deviceId,
      field: selectedField.value,
      usl: spec.usl,
      lsl: spec.lsl,
    })
  } finally {
    loading.value = false
  }
}

async function loadOverview() {
  if (!filter.deviceId) return
  loading.value = true
  try {
    spcResult.value = await fetchSpc({ device_id: filter.deviceId })
    if (spcResult.value.overview.length && !selectedField.value) {
      selectedField.value = spcResult.value.overview[0].field
      await loadSpc()
    }
  } finally {
    loading.value = false
  }
}

async function handleQuery() {
  localStorage.setItem(SAVED_DEVICE_KEY, filter.deviceId)
  selectedField.value = ''
  await loadOverview()
}

function toggleMonitoring() {
  monitoring.value = !monitoring.value
  if (monitoring.value) {
    countdown.value = monitorInterval.value
    monitorTimer = setInterval(async () => {
      if (filter.deviceId && selectedField.value) {
        try {
          await loadSpc()
        } catch {
        }
      }
      countdown.value = monitorInterval.value
    }, monitorInterval.value * 1000)
    countdownTimer = setInterval(() => {
      if (countdown.value > 0) countdown.value--
    }, 1000)
  } else {
    clearInterval(monitorTimer)
    clearInterval(countdownTimer)
    monitorTimer = undefined
    countdownTimer = undefined
  }
}

watch(() => app.fullscreen, (val) => {
  if (val) {
    document.addEventListener('keydown', handleEsc)
  } else {
    document.removeEventListener('keydown', handleEsc)
  }
})

function handleEsc(e: KeyboardEvent) {
  if (e.key === 'Escape') app.exitFullscreen()
}

onMounted(async () => {
  try {
    devices.value = await listDevices()
    if (filter.deviceId && devices.value.includes(filter.deviceId)) {
      await loadOverview()
    }
  } catch {
    // silently fail
  }
})

onUnmounted(() => {
  clearInterval(monitorTimer)
  clearInterval(countdownTimer)
  app.exitFullscreen()
})

watchEffect(async () => {
  const deviceId = route.query.device as string | undefined
  if (deviceId) {
    try {
      deviceInfo.value = await getDevice(deviceId)
      if (deviceInfo.value?.line_id) {
        const line = await getLine(deviceInfo.value.line_id)
        lineName.value = line.name
      }
    } catch { deviceInfo.value = null }
  } else {
    deviceInfo.value = null
    lineName.value = ''
  }
})

async function saveDeviceInfo() {
  if (!deviceInfo.value) return
  savingDevice.value = true
  try {
    await updateDevice(deviceInfo.value.id, deviceForm.value)
    editingDevice.value = false
    // Reload device info
    deviceInfo.value = await getDevice(deviceInfo.value.id)
  } finally { savingDevice.value = false }
}

watch(editingDevice, (val) => {
  if (val && deviceInfo.value) {
    deviceForm.value = {
      name: deviceInfo.value.name,
      type: deviceInfo.value.type,
      icon: deviceInfo.value.icon || '',
      description: deviceInfo.value.description || '',
    }
  }
})

const C = {
  line: '#3B82F6',
  lineLight: '#60A5FA',
  center: '#059669',
  limit: '#DC2626',
  bar: '#3B82F6',
  curve: '#DC2626',
  area: '#BFDBFE',
}

function buildIChartOption(chart: SpcResult['i_chart']) {
  if (!chart) return {}
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 25, bottom: 25 },
    xAxis: { type: 'category', data: chart.labels, axisLabel: { rotate: 45, fontSize: 9 }, axisLine: { show: false }, axisTick: { show: false } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#334155', type: 'dashed' } } },
    series: [
      {
        type: 'line',
        data: chart.values,
        smooth: true,
        symbol: 'circle',
        symbolSize: 4,
        lineStyle: { width: 1.5, color: C.line },
        areaStyle: { color: C.area, opacity: 0.15 },
        itemStyle: {
          color: (params: any) => chart.alerts.includes(params.dataIndex) ? C.limit : C.line,
        },
        markLine: {
          silent: true,
          symbol: 'none',
          data: [
            { yAxis: chart.mean, label: { formatter: `CL: ${chart.mean.toFixed(1)}`, fontSize: 9, color: C.center }, lineStyle: { type: 'solid', color: C.center, width: 1 } },
            { yAxis: chart.ucl, label: { formatter: `UCL: ${chart.ucl.toFixed(1)}`, fontSize: 9, color: C.limit }, lineStyle: { type: 'dashed', color: C.limit, width: 1 } },
            { yAxis: chart.lcl, label: { formatter: `LCL: ${chart.lcl.toFixed(1)}`, fontSize: 9, color: C.limit }, lineStyle: { type: 'dashed', color: C.limit, width: 1 } },
          ],
        },
      },
    ],
  }
}

function buildMrChartOption(chart: SpcResult['mr_chart']) {
  if (!chart) return {}
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 25, bottom: 25 },
    xAxis: { type: 'category', data: chart.labels, axisLabel: { rotate: 45, fontSize: 9 }, axisLine: { show: false }, axisTick: { show: false } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#334155', type: 'dashed' } } },
    series: [
      {
        type: 'line',
        data: chart.values,
        step: 'end',
        symbol: 'circle',
        symbolSize: 4,
        lineStyle: { width: 1.5, color: C.lineLight },
        areaStyle: { color: C.area, opacity: 0.1 },
        markLine: {
          silent: true,
          symbol: 'none',
          data: [
            { yAxis: chart.mr_bar, label: { formatter: `MR̄: ${chart.mr_bar.toFixed(1)}`, fontSize: 9, color: C.center }, lineStyle: { type: 'solid', color: C.center, width: 1 } },
            { yAxis: chart.ucl, label: { formatter: `UCL: ${chart.ucl.toFixed(1)}`, fontSize: 9, color: C.limit }, lineStyle: { type: 'dashed', color: C.limit, width: 1 } },
          ],
        },
      },
    ],
  }
}

function buildHistogramOption(hist: SpcResult['histogram'], cap: SpcResult['capability']) {
  if (!hist || !cap) return {}
  const labels = hist.bins.map((b) => {
    const halfBin = (hist.bins[1] - hist.bins[0]) / 2 || 5
    return `${(b - halfBin).toFixed(1)}~${(b + halfBin).toFixed(1)}`
  })
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 12, right: 12, top: 30, bottom: 30 },
    xAxis: { type: 'category', data: labels, axisLabel: { rotate: 60, fontSize: 8, interval: 2 }, axisLine: { show: false }, axisTick: { show: false } },
    yAxis: { type: 'value', show: false, splitLine: { show: false } },
    series: [
      {
        name: '频次',
        type: 'bar',
        data: hist.counts,
        barWidth: '80%',
        itemStyle: { color: C.bar, opacity: 0.5 },
      },
    ],
  }
}

function buildPChartOption(chart: SpcResult['p_chart']) {
  if (!chart) return {}
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 25, bottom: 25 },
    xAxis: { type: 'category', data: chart.periods, axisLabel: { rotate: 45, fontSize: 9 }, axisLine: { show: false }, axisTick: { show: false } },
    yAxis: { type: 'value', axisLabel: { formatter: '{value}%', fontSize: 9 }, splitLine: { lineStyle: { color: '#334155', type: 'dashed' } } },
    series: [
      {
        type: 'line',
        data: chart.rates.map((r) => +(r * 100).toFixed(2)),
        symbol: 'diamond',
        symbolSize: 6,
        lineStyle: { width: 1.5, color: C.line },
        areaStyle: { color: C.area, opacity: 0.15 },
        markLine: {
          silent: true,
          symbol: 'none',
          data: [
            { yAxis: chart.p_bar * 100, label: { formatter: `p̄: ${(chart.p_bar * 100).toFixed(1)}%`, fontSize: 9, color: C.center }, lineStyle: { type: 'solid', color: C.center, width: 1 } },
            { yAxis: chart.ucl * 100, label: { formatter: `UCL: ${(chart.ucl * 100).toFixed(1)}%`, fontSize: 9, color: C.limit }, lineStyle: { type: 'dashed', color: C.limit, width: 1 } },
          ],
        },
      },
    ],
  }
}

function buildCapabilityOption(cap: SpcResult['capability']) {
  if (!cap) return {}
  return {
    tooltip: { trigger: 'item' },
    grid: { left: 10, right: 10, top: 10, bottom: 10 },
    xAxis: { type: 'category', axisLine: { show: false }, axisTick: { show: false }, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', show: false },
    series: [
      {
        type: 'bar',
        data: [
          { name: 'Cp', value: cap.cp },
          { name: 'Cpk', value: cap.cpk },
          { name: 'Pp', value: cap.pp },
          { name: 'Ppk', value: cap.ppk },
        ],
        barWidth: 18,
        label: {
          show: true,
          position: 'top',
          formatter: (p: any) => p.value.toFixed(2),
          fontSize: 10,
          fontFamily: 'Fira Code, monospace',
        },
        itemStyle: {
          color: (p: any) => {
            const v = p.value
            return v >= 1.33 ? '#059669' : v >= 1.0 ? '#D97706' : '#DC2626'
          },
          borderRadius: [2, 2, 0, 0],
        },
      },
    ],
  }
}

function buildSummaryOption(summary: SpcResult['summary'], cap: SpcResult['capability']) {
  if (!summary) return {}
  const lines = [
    `N: ${summary.n}`,
    `Mean: ${summary.mean.toFixed(2)}`,
    `Std: ${summary.std.toFixed(2)}`,
    `Min: ${summary.min_val}`,
    `Max: ${summary.max_val}`,
    `USL: ${cap?.usl.toFixed(2) ?? '-'}`,
    `LSL: ${cap?.lsl.toFixed(2) ?? '-'}`,
  ]
  return {
    series: [],
    graphic: [
      {
        type: 'text',
        left: 'center',
        top: 'center',
        style: {
          text: lines.join('\n'),
          fontSize: 11,
          lineHeight: 20,
          fontFamily: 'Fira Code, monospace',
          textAlign: 'center',
          fill: '#94A3B8',
        },
      },
    ],
  }
}
</script>

<style scoped>
.spc-view {
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-bottom: 16px;
}
.spc-header {
  flex-shrink: 0;
  margin-bottom: 0;
}
.page-title {
  font-family: 'Fira Code', monospace;
  font-size: 20px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0 0 2px;
}
.page-desc {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin: 0;
}
.spc-filter-card {
  flex-shrink: 0;
  margin-bottom: 0;
}
.spc-filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 4px;
}
.spc-monitor-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}
.monitor-interval {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.fullscreen-btn {
  color: var(--el-text-color-secondary);
  padding: 4px;
}
.fullscreen-btn:hover {
  color: var(--el-text-color-primary);
}
.monitor-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: rgba(239, 68, 68, 0.08);
  border-radius: 4px;
  font-size: 12px;
  color: #DC2626;
  margin-top: 8px;
}
.monitor-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #DC2626;
  animation: pulse 1.5s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
.overview-card {
  flex-shrink: 0;
}
.overview-card :deep(.el-card__header) {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
}
.section-title {
  font-size: 13px;
  font-weight: 500;
}
.section-subtitle {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
.spc-charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 10px;
}
.chart-card {
  display: flex;
  flex-direction: column;
}
.chart-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  padding: 4px;
}
.chart-card :deep(.el-card__header) {
  padding: 4px 8px;
}
.chart-body {
  width: 100%;
}
.chart-title {
  font-size: 12px;
  font-weight: 500;
  color: var(--el-text-color-secondary);
}
.spc-breadcrumb {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 12px; background: var(--el-fill-color-light);
  border-radius: 6px; font-size: 12px;
}
.bc-link { color: var(--el-color-primary); text-decoration: none; }
.bc-link:hover { text-decoration: underline; }
.bc-sep { color: var(--el-text-color-placeholder); }
.bc-current { color: var(--el-text-color-primary); font-weight: 500; }
.device-info-bar {
  display: flex; gap: 24px; padding: 4px 12px;
  font-size: 12px; color: var(--el-text-color-regular);
}
.info-label { color: var(--el-text-color-secondary); margin-right: 4px; }
</style>

<template>
  <div>
    <div v-if="!autoMode" class="correlation-form">
      <el-form inline>
        <el-form-item label="参数 X">
          <el-select v-model="fieldX" style="width: 180px">
            <el-option v-for="f in allFields" :key="f" :label="f" :value="f" />
          </el-select>
        </el-form-item>
        <el-form-item label="参数 Y">
          <el-select v-model="fieldY" style="width: 180px">
            <el-option v-for="f in allFields" :key="f" :label="f" :value="f" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleCompute" :loading="loading">计算</el-button>
        </el-form-item>
      </el-form>
    </div>
    <div class="chart-wrapper" v-loading="loading">
      <div v-if="results.length && !autoMode" class="single-result">
        <div class="single-value">
          <span class="correlation-pair">{{ results[0].field_x }} × {{ results[0].field_y }}</span>
          <span class="correlation-coeff" :style="{ color: coeffColor(results[0].coefficient) }">
            r = {{ results[0].coefficient.toFixed(4) }}
          </span>
          <span class="correlation-p">p = {{ results[0].p_value.toFixed(4) }}</span>
        </div>
      </div>
      <div v-if="matrixData.length" class="heatmap-container">
        <div ref="chartRef" class="heatmap-chart" />
        <div class="heatmap-legend">
          <span class="legend-label">-1</span>
          <div class="legend-bar" />
          <span class="legend-label">+1</span>
        </div>
        <div class="legend-scale">
          <span>极弱</span><span>弱</span><span>中</span><span>强</span>
        </div>
      </div>
      <el-empty v-if="!results.length && !matrixData.length" :description="autoMode ? '请先执行分析' : '选择参数后点击计算'" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { correlation } from '@/api/analysis'
import * as echarts from 'echarts'

const props = defineProps<{
  datasetId: string
  featureFields: string[]
  targetFields: string[]
  autoMode?: boolean
}>()

const loading = ref(false)
const fieldX = ref('')
const fieldY = ref('')
const results = ref<{ field_x: string; field_y: string; coefficient: number; p_value: number; method: string }[]>([])
const matrixData = ref<{ x: string; y: string; value: number }[]>([])
const chartRef = ref<HTMLDivElement>()

const allFields = computed(() => [...props.featureFields, ...props.targetFields])

function coeffColor(r: number): string {
  const absR = Math.abs(r)
  if (absR > 0.7) return '#ef4444'
  if (absR > 0.5) return '#f97316'
  if (absR > 0.3) return '#eab308'
  return '#3b82f6'
}

async function handleCompute() {
  if (!fieldX.value || !fieldY.value) return
  loading.value = true
  try {
    const r = await correlation({
      dataset_id: props.datasetId,
      field_x: fieldX.value,
      field_y: fieldY.value,
      method: 'pearson',
    }) as { field_x: string; field_y: string; coefficient: number; p_value: number; method: string }
    results.value = [r]
  } finally {
    loading.value = false
  }
}

watch(() => props.autoMode, (v) => {
  if (v) autoCompute()
}, { immediate: true })

watch(() => [props.datasetId, props.featureFields.length, props.targetFields.length], () => {
  if (props.autoMode) autoCompute()
})

async function autoCompute() {
  if (!props.datasetId || !props.featureFields.length || !props.targetFields.length) return
  loading.value = true
  try {
    const data = await correlation({
      dataset_id: props.datasetId,
      method: 'pearson',
    }) as unknown as { field_x: string; field_y: string; coefficient: number; p_value: number; method: string }[]
    results.value = data
    buildMatrix(data)
  } finally {
    loading.value = false
  }
}

function buildMatrix(data: { field_x: string; field_y: string; coefficient: number }[]) {
  const xSet = new Set<string>()
  const ySet = new Set<string>()
  for (const d of data) {
    xSet.add(d.field_x)
    ySet.add(d.field_y)
  }
  const xLabels = Array.from(xSet)
  const yLabels = Array.from(ySet)
  const map = new Map<string, number>()
  for (const d of data) {
    map.set(`${d.field_x}|${d.field_y}`, d.coefficient)
  }
  const items: { x: string; y: string; value: number }[] = []
  for (const y of yLabels) {
    for (const x of xLabels) {
      const v = map.get(`${x}|${y}`)
      if (v !== undefined) {
        items.push({ x, y, value: v })
      }
    }
  }
  matrixData.value = items
  nextTick(() => renderHeatmap(xLabels, yLabels, items))
}

function renderHeatmap(xLabels: string[], yLabels: string[], items: { x: string; y: string; value: number }[]) {
  if (!chartRef.value) return
  const chart = echarts.init(chartRef.value)
  const heatData = items.map(i => [xLabels.indexOf(i.x), yLabels.indexOf(i.y), i.value])
  chart.setOption({
    tooltip: {
      formatter: (p: any) => {
        const d = items[p.dataIndex]
        const absR = Math.abs(d.value)
        let strength = '极弱'
        if (absR > 0.7) strength = '强'
        else if (absR > 0.5) strength = '中'
        else if (absR > 0.3) strength = '弱'
        return `${d.x} × ${d.y}<br/>r = ${d.value.toFixed(4)} (${strength})`
      },
    },
    grid: { left: 120, right: 60, top: 40, bottom: 60 },
    visualMap: {
      min: -1,
      max: 1,
      inRange: {
        color: ['#3b82f6', '#eab308', '#f97316', '#ef4444'],
      },
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      textStyle: { fontSize: 11 },
    },
    series: [{
      type: 'heatmap',
      data: heatData,
      label: {
        show: true,
        formatter: (p: any) => heatData[p.dataIndex][2].toFixed(2),
        fontSize: 10,
        color: '#333',
      },
      emphasis: {
        itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,0,0,0.3)' },
      },
    }],
  })
  window.addEventListener('resize', () => chart.resize())
}
</script>

<style scoped>
.correlation-form { margin-bottom: 12px; }
.chart-wrapper { min-height: 200px; }
.single-result {
  background: var(--el-bg-color);
  border-radius: 6px;
  padding: 14px;
  border: 1px solid var(--el-border-color-light);
}
.single-value {
  display: flex;
  gap: 16px;
  align-items: center;
}
.correlation-pair {
  font-family: 'Fira Code', monospace;
  font-weight: 600;
  font-size: 13px;
  color: var(--el-color-primary);
}
.correlation-coeff { font-weight: 600; font-size: 15px; }
.correlation-p { font-size: 12px; color: var(--el-text-color-secondary); }
.heatmap-container {
  min-height: 300px;
  display: flex;
  flex-direction: column;
}
.heatmap-chart {
  flex: 1;
  min-height: 350px;
  width: 100%;
}
.heatmap-legend {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin-top: 4px;
}
.legend-label { font-size: 11px; color: var(--el-text-color-secondary); }
.legend-bar {
  width: 80px;
  height: 10px;
  border-radius: 3px;
  background: linear-gradient(to right, #3b82f6, #eab308, #f97316, #ef4444);
}
.legend-bar2 {
  width: 80px;
  height: 10px;
  border-radius: 3px;
  background: linear-gradient(to right, #ef4444, #f97316, #eab308, #3b82f6);
}
.legend-scale { display: flex; justify-content: space-between; width: 80px; font-size: 10px; color: var(--el-text-color-secondary); }
</style>
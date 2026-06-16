<template>
  <div class="pareto-chart">
    <div v-if="!autoMode" class="pareto-form">
      <el-form inline>
        <el-form-item label="目标 Y">
          <el-select v-model="targetField" style="width: 180px">
            <el-option v-for="f in targetFields" :key="f" :label="f" :value="f" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleCompute" :loading="loading">计算</el-button>
        </el-form-item>
      </el-form>
    </div>
    <div class="chart-wrapper" v-loading="loading">
      <div v-if="items.length" ref="chartRef" class="pareto-chart-el" />
      <div v-if="items.length" class="pareto-insights">
        <div class="insight-card">
          <div class="insight-label">80/20 分析</div>
          <div class="insight-value">前 3 个因子贡献 <strong>{{ topContrib }}%</strong></div>
        </div>
        <div class="insight-card">
          <div class="insight-label">建议优先优化</div>
          <div class="insight-tags">
            <el-tag v-for="item in topFactors" :key="item.field" :type="tagType(item.strength)" size="small">
              {{ item.field }} ({{ item.coefficient }})
            </el-tag>
          </div>
        </div>
      </div>
      <el-empty v-if="!items.length && !loading" description="选择目标后点击计算" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { computePareto, type ParetoItem } from '@/api/analysis'
import * as echarts from 'echarts'

const props = defineProps<{
  datasetId: string
  targetFields: string[]
  autoMode?: boolean
}>()

const loading = ref(false)
const targetField = ref('')
const items = ref<ParetoItem[]>([])
const chartRef = ref<HTMLDivElement>()

const topFactors = computed(() => items.value.slice(0, 3))
const topContrib = computed(() => {
  if (!items.value.length) return '0'
  return items.value.slice(0, 3).reduce((s, i) => s + i.contribution_pct, 0).toFixed(1)
})

function tagType(strength: string): 'danger' | 'warning' | 'info' | '' {
  if (strength === 'strong') return 'danger'
  if (strength === 'medium') return 'warning'
  if (strength === 'weak') return 'info'
  return ''
}

watch(() => props.autoMode, (v) => { if (v) autoCompute() }, { immediate: true })
watch(() => [props.datasetId, props.targetFields.length], () => {
  if (props.autoMode) autoCompute()
})

async function autoCompute() {
  if (!props.datasetId || !props.targetFields.length) return
  targetField.value = props.targetFields[0]
  await handleCompute()
}

async function handleCompute() {
  if (!targetField.value) return
  loading.value = true
  try {
    items.value = await computePareto({
      dataset_id: props.datasetId,
      field_y: targetField.value,
    })
    await nextTick()
    renderChart()
  } finally {
    loading.value = false
  }
}

function renderChart() {
  if (!chartRef.value || !items.value.length) return
  const chart = echarts.init(chartRef.value)
  const names = items.value.map(i => i.field)

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: (params: any[]) => {
        const idx = params[0].dataIndex
        const item = items.value[idx]
        return `<strong>${item.field}</strong><br/>
          |r| = ${item.coefficient}<br/>
          贡献率: ${item.contribution_pct}%<br/>
          累计: ${item.cumulative_pct}%<br/>
          强度: ${item.strength}`
      },
    },
    grid: { left: 60, right: 60, top: 30, bottom: 50 },
    xAxis: {
      type: 'category',
      data: names,
      axisLabel: { rotate: 30, fontSize: 11, interval: 0 },
    },
    yAxis: [
      {
        type: 'value',
        name: '贡献率 %',
        nameTextStyle: { fontSize: 11 },
        max: 100,
        axisLabel: { fontSize: 11 },
      },
      {
        type: 'value',
        name: '累计 %',
        nameTextStyle: { fontSize: 11 },
        max: 100,
        axisLabel: { fontSize: 11 },
      },
    ],
    series: [
      {
        name: '贡献率',
        type: 'bar',
        data: items.value.map(i => i.contribution_pct),
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#3b82f6' },
            { offset: 1, color: '#1d4ed8' },
          ]),
        },
      },
      {
        name: '累计贡献率',
        type: 'line',
        yAxisIndex: 1,
        data: items.value.map(i => i.cumulative_pct),
        lineStyle: { color: '#ef4444', width: 2, type: 'dashed' },
        itemStyle: { color: '#ef4444' },
        markLine: {
          silent: true,
          data: [{ yAxis: 80, label: { formatter: '80%', fontSize: 10 } }],
          lineStyle: { color: '#f97316', type: 'dashed' },
        },
      },
    ],
  })
  window.addEventListener('resize', () => chart.resize())
}
</script>

<style scoped>
.pareto-form { margin-bottom: 12px; }
.chart-wrapper { min-height: 200px; }
.pareto-chart-el { width: 100%; height: 320px; }
.pareto-insights { display: flex; gap: 12px; margin-top: 12px; }
.insight-card {
  flex: 1; background: var(--el-bg-color);
  border-radius: 6px; padding: 10px 14px;
  border: 1px solid var(--el-border-color-light);
}
.insight-label { font-size: 11px; color: var(--el-text-color-secondary); margin-bottom: 4px; }
.insight-value { font-size: 13px; color: var(--el-text-color-primary); }
.insight-value strong { color: var(--el-color-warning); }
.insight-tags { display: flex; gap: 4px; flex-wrap: wrap; }
</style>

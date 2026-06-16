<template>
  <div class="cpk-optimizer">
    <div class="opt-config">
      <el-form label-width="100px" size="small">
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="目标 Cpk">
              <el-input-number v-model="targetCpk" :min="0.5" :max="3" :step="0.1" style="width: 140px" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="USL">
              <el-input-number v-model="uslVal" :min="0" :step="1" style="width: 140px" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="LSL">
              <el-input-number v-model="lslVal" :min="0" :step="1" style="width: 140px" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="目标值">
              <el-input-number v-model="targetVal" :min="0" :step="0.5" style="width: 140px" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="搜索步长">
              <el-slider v-model="stepSize" :min="0.1" :max="5" :step="0.1" style="width: 160px" />
              <span class="slider-val">{{ stepSize }}</span>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="关键因子">
          <el-checkbox-group v-model="selectedFactors">
            <el-checkbox v-for="f in featureFields" :key="f" :label="f" :value="f" />
          </el-checkbox-group>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleOptimize" :loading="loading" :disabled="!selectedFactors.length">
            <el-icon style="margin-right: 4px;"><Aim /></el-icon> 开始优化
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <div v-if="result" class="opt-results">
      <div class="cpk-comparison">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-card shadow="never">
              <div class="cpk-label">优化前 Cpk</div>
              <div class="cpk-value initial">{{ result.initial_cpk }}</div>
              <div class="cpk-status" :class="cpkClass(result.initial_cpk)">{{ cpkText(result.initial_cpk) }}</div>
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card shadow="never">
              <div class="cpk-label">优化后 Cpk</div>
              <div class="cpk-value optimized">{{ result.optimized_cpk }}</div>
              <div class="cpk-status" :class="cpkClass(result.optimized_cpk)">{{ cpkText(result.optimized_cpk) }}</div>
            </el-card>
          </el-col>
        </el-row>
      </div>

      <div class="convergence-section">
        <h4 class="section-title">收敛轨迹</h4>
        <div ref="convChartRef" class="conv-chart" />
      </div>

      <div class="adjustments-section">
        <h4 class="section-title">参数调整建议</h4>
        <el-table :data="adjustmentRows" border size="small" style="width: 100%">
          <el-table-column label="参数" prop="field" width="120" />
          <el-table-column label="当前值" prop="from" width="100" />
          <el-table-column label="优化值" prop="to" width="100" />
          <el-table-column label="调整量" prop="delta" width="100">
            <template #default="{ row }">
              <span :style="{ color: row.delta > 0 ? 'var(--el-color-danger)' : 'var(--el-color-success)' }">
                {{ row.delta > 0 ? '+' : '' }}{{ row.delta }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="方向" width="80">
            <template #default="{ row }">
              <el-tag v-if="row.delta > 0" type="danger" size="small">上调</el-tag>
              <el-tag v-else-if="row.delta < 0" type="success" size="small">下调</el-tag>
              <el-tag v-else type="info" size="small">不变</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="submit-section">
        <el-button type="primary" @click="handleSubmit" size="default">
          <el-icon style="margin-right: 4px;"><Upload /></el-icon> 提交到参数管理
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import { optimizeCpk, type OptimizationResult } from '@/api/analysis'
import { createSet } from '@/api/parameters'
import * as echarts from 'echarts'
import { Aim, Upload } from '@element-plus/icons-vue'

const props = defineProps<{
  datasetId: string
  featureFields: string[]
  targetField: string
  usl: number
  lsl: number
  targetValue: number
}>()

const loading = ref(false)
const result = ref<OptimizationResult | null>(null)
const convChartRef = ref<HTMLDivElement>()

const targetCpk = ref(1.33)
const uslVal = ref(props.usl)
const lslVal = ref(props.lsl)
const targetVal = ref(props.targetValue)
const stepSize = ref(1.0)
const selectedFactors = ref<string[]>([])

watch(() => props.featureFields, (fields) => {
  if (!selectedFactors.value.length) {
    selectedFactors.value = fields.slice(0, 3)
  }
}, { immediate: true })

watch(() => props.usl, (v) => { uslVal.value = v })
watch(() => props.lsl, (v) => { lslVal.value = v })
watch(() => props.targetValue, (v) => { targetVal.value = v })

const adjustmentRows = computed(() => {
  if (!result.value) return []
  return Object.entries(result.value.parameter_adjustments).map(([field, adj]) => ({
    field, ...adj,
  }))
})

function cpkClass(cpk: number): string {
  if (cpk >= 1.33) return 'normal'
  if (cpk >= 1.0) return 'marginal'
  return 'abnormal'
}

function cpkText(cpk: number): string {
  if (cpk >= 1.33) return '达标'
  if (cpk >= 1.0) return '边缘'
  return '异常'
}

async function handleOptimize() {
  if (!selectedFactors.value.length) return
  loading.value = true
  result.value = null
  try {
    result.value = await optimizeCpk({
      dataset_id: props.datasetId,
      target_field: props.targetField,
      usl: uslVal.value,
      lsl: lslVal.value,
      target_value: targetVal.value,
      target_cpk: targetCpk.value,
      key_factors: selectedFactors.value,
      step_size: stepSize.value,
    })
    await nextTick()
    renderConvergence()
  } finally {
    loading.value = false
  }
}

function renderConvergence() {
  if (!convChartRef.value || !result.value) return
  const chart = echarts.init(convChartRef.value)
  const data = result.value.convergence

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: (params: any[]) => `迭代: ${params[0].dataIndex * 50}<br/>Cpk: ${params[0].value}`,
    },
    grid: { left: 50, right: 30, top: 30, bottom: 30 },
    xAxis: {
      type: 'category',
      data: data.map(d => d.iteration),
      name: '迭代次数',
      nameTextStyle: { fontSize: 11 },
      axisLabel: { fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      name: 'Cpk',
      nameTextStyle: { fontSize: 11 },
      axisLabel: { fontSize: 11 },
    },
    series: [{
      type: 'line',
      data: data.map(d => d.cpk_value),
      smooth: true,
      lineStyle: { color: '#6366f1', width: 2 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(99,102,241,0.3)' },
          { offset: 1, color: 'rgba(99,102,241,0.05)' },
        ]),
      },
      markLine: {
        silent: true,
        data: [{ yAxis: targetCpk.value, label: { formatter: `目标 Cpk = ${targetCpk.value}`, fontSize: 10 } }],
        lineStyle: { color: '#10b981', type: 'dashed' },
      },
    }],
  })
  window.addEventListener('resize', () => chart.resize())
}

async function handleSubmit() {
  if (!result.value) return
  await createSet({
    name: `Cpk Optimization - ${props.targetField}`,
    device_type: 'imported',
    items: Object.entries(result.value.recommended_params).map(([key, value]) => ({
      param_name: key,
      param_value: value,
    })),
  })
}
</script>

<style scoped>
.opt-config { margin-bottom: 16px; }
.slider-val { margin-left: 8px; font-family: 'Fira Code', monospace; font-size: 12px; color: var(--el-text-color-secondary); }
.opt-results { margin-top: 16px; }
.cpk-comparison { margin-bottom: 20px; }
.cpk-label { font-size: 11px; color: var(--el-text-color-secondary); margin-bottom: 4px; }
.cpk-value { font-family: 'Fira Code', monospace; font-size: 28px; font-weight: 700; }
.cpk-value.initial { color: var(--el-color-danger); }
.cpk-value.optimized { color: var(--el-color-success); }
.cpk-status { font-size: 12px; margin-top: 4px; }
.cpk-status.normal { color: var(--el-color-success); }
.cpk-status.marginal { color: var(--el-color-warning); }
.cpk-status.abnormal { color: var(--el-color-danger); }
.section-title { font-size: 13px; font-weight: 600; margin: 0 0 8px; color: var(--el-text-color-primary); }
.conv-chart { width: 100%; height: 240px; margin-bottom: 20px; }
.adjustments-section { margin-bottom: 16px; }
.submit-section { margin-top: 12px; }
</style>

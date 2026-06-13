<template>
  <div>
    <div v-if="!autoMode" class="regression-form">
      <el-form inline>
        <el-form-item label="目标结果">
          <el-select v-model="targetField" style="width: 180px">
            <el-option v-for="f in props.targetFields" :key="f" :label="f" :value="f" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleCompute" :loading="loading">计算</el-button>
        </el-form-item>
      </el-form>
    </div>
    <div class="chart-wrapper">
      <div v-for="r in results" :key="r.target" class="regression-card">
        <div class="regression-target">{{ r.target }}</div>
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="R²">{{ r.r_squared.toFixed(4) }}</el-descriptions-item>
          <el-descriptions-item label="RMSE">{{ r.rmse.toFixed(4) }}</el-descriptions-item>
          <el-descriptions-item label="模型">{{ r.model_type }}</el-descriptions-item>
        </el-descriptions>
      </div>
      <el-empty v-if="!results.length && !loading" description="选择参数后点击计算" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { regression } from '@/api/analysis'

const props = defineProps<{
  datasetId: string
  featureFields: string[]
  targetFields: string[]
  autoMode?: boolean
}>()

const loading = ref(false)
const targetField = ref('')
const results = ref<{ target: string; r_squared: number; rmse: number; model_type: string }[]>([])

async function handleCompute() {
  if (!targetField.value || !props.featureFields.length) return
  loading.value = true
  try {
    const r = await regression({
      dataset_id: props.datasetId,
      feature_fields: props.featureFields,
      target_field: targetField.value,
      model_type: 'linear',
    }) as { r_squared: number; rmse: number; model_type: string }
    results.value = [{ target: targetField.value, ...r }]
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
  const out: { target: string; r_squared: number; rmse: number; model_type: string }[] = []
  try {
    for (const t of props.targetFields) {
      const r = await regression({
        dataset_id: props.datasetId,
        feature_fields: props.featureFields,
        target_field: t,
        model_type: 'linear',
      }) as { r_squared: number; rmse: number; model_type: string }
      out.push({ target: t, ...r })
    }
    results.value = out
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.regression-form { margin-bottom: 12px; }
.chart-wrapper { min-height: 120px; }
.regression-card {
  background: var(--el-bg-color);
  border-radius: 6px;
  padding: 10px 14px;
  border: 1px solid var(--el-border-color-light);
  margin-bottom: 8px;
}
.regression-target {
  font-family: 'Fira Code', monospace;
  font-size: 13px;
  font-weight: 500;
  color: var(--el-color-primary);
  margin-bottom: 8px;
}
</style>

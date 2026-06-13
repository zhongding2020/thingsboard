<template>
  <div>
    <div class="rec-form">
      <el-form label-width="100px">
        <el-form-item label="目标字段">
          <el-select v-model="cfg.targetField" style="width: 200px">
            <el-option v-for="f in props.targetFields" :key="f" :label="f" :value="f" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标值">
          <el-input-number v-model="cfg.targetValue" :min="0" :step="0.1" />
        </el-form-item>
        <el-form-item v-for="f in props.featureFields" :key="f" :label="f">
          <el-slider v-model="cfg.constraints[f]" :min="0" :max="500" :step="0.5" style="width: 260px" />
          <span class="slider-val">{{ cfg.constraints[f].toFixed(1) }}</span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleCompute" :loading="loading">计算推荐</el-button>
        </el-form-item>
      </el-form>
    </div>
    <div v-if="result" class="rec-result">
      <h4>推荐参数</h4>
      <div v-for="(v, k) in result.recommended_parameters" :key="k" class="rec-row">
        <span class="rec-name">{{ k }}</span>
        <span class="rec-value">{{ v.toFixed(1) }}</span>
      </div>
      <div class="rec-prediction">预期目标值: {{ result.predicted_target.toFixed(4) }}</div>
      <div v-if="result.risk_notes.length" class="risk-notes">
        <p v-for="(n, i) in result.risk_notes" :key="i" class="risk-note">⚠ {{ n }}</p>
      </div>
      <el-button type="success" size="small" @click="handleSubmit" style="margin-top: 12px;">提交到参数管理</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { recommendation, submitRecommendation } from '@/api/analysis'

const props = defineProps<{
  datasetId: string
  featureFields: string[]
  targetFields: string[]
}>()

const loading = ref(false)
const result = ref<{
  recommended_parameters: Record<string, number>
  predicted_target: number
  risk_notes: string[]
} | null>(null)

const cfg = reactive<{
  targetField: string
  targetValue: number
  constraints: Record<string, number>
}>({
  targetField: '',
  targetValue: 0,
  constraints: {},
})

async function handleCompute() {
  if (!cfg.targetField || !props.featureFields.length) return
  loading.value = true
  try {
    const constraints = Object.entries(cfg.constraints).map(([field, max]) => ({
      field,
      max: max || undefined,
    }))
    result.value = await recommendation({
      dataset_id: props.datasetId,
      feature_fields: props.featureFields,
      target_field: cfg.targetField,
      target_value: cfg.targetValue,
      constraints,
    }) as typeof result.value
  } finally {
    loading.value = false
  }
}

async function handleSubmit() {
  if (!result.value) return
  await submitRecommendation({
    device_type: 'imported',
    parameters: result.value.recommended_parameters,
  })
}
</script>

<style scoped>
.rec-form { margin-bottom: 16px; }
.slider-val { margin-left: 10px; font-family: 'Fira Code', monospace; font-size: 12px; color: var(--el-text-color-secondary); }
.rec-result { background: var(--el-bg-color); border-radius: 8px; padding: 14px; border: 1px solid var(--el-border-color-light); }
.rec-result h4 { font-size: 13px; font-weight: 600; margin: 0 0 8px; }
.rec-row { display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid var(--el-border-color-light); }
.rec-name { font-family: 'Fira Code', monospace; font-size: 13px; color: var(--el-color-primary); }
.rec-value { font-family: 'Fira Code', monospace; font-size: 13px; font-weight: 500; }
.rec-prediction { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 8px; }
.risk-notes { margin-top: 8px; }
.risk-note { font-size: 11px; color: var(--el-color-warning); margin: 2px 0; }
</style>

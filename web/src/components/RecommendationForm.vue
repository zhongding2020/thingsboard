<template>
  <div class="recommendation-form">
    <el-card shadow="hover">
      <template #header>参数优化推荐</template>
      <el-form :model="form" label-width="120px">
        <el-form-item label="目标结果">
          <el-select v-model="form.targetField" :disabled="!allFields.length" style="width: 200px">
            <el-option v-for="f in allFields" :key="f" :label="f" :value="f" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标值">
          <el-input-number v-model="form.targetValue" :min="0" :max="9999" :step="0.1" />
        </el-form-item>
        <el-form-item v-for="(_, key) in form.params" :key="key" :label="key">
          <el-slider
            v-model="form.params[key].value"
            :min="form.params[key].min"
            :max="form.params[key].max"
            :step="0.1"
            style="width: 300px"
          />
          <span class="param-value">{{ form.params[key].value.toFixed(1) }}</span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSubmit" :loading="loading">提交推荐</el-button>
        </el-form-item>
      </el-form>
    </el-card>
    <el-card v-if="analysis.recommendationResult" shadow="hover" class="result-card">
      <template #header>推荐结果</template>
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="预期目标值">
          {{ analysis.recommendationResult.predicted_target.toFixed(4) }}
        </el-descriptions-item>
      </el-descriptions>
      <div class="recommend-params">
        <h4>推荐参数</h4>
        <div v-for="(v, k) in analysis.recommendationResult.recommended_parameters" :key="k" class="rec-row">
          <span class="rec-name">{{ k }}</span>
          <span class="rec-value">{{ v.toFixed(1) }}</span>
        </div>
      </div>
      <div v-if="analysis.recommendationResult.risk_notes.length" class="risk-notes">
        <h4>风险提示</h4>
        <p v-for="(note, i) in analysis.recommendationResult.risk_notes" :key="i" class="risk-note">{{ note }}</p>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed, watchEffect } from 'vue'
import { useAnalysisStore } from '@/stores/analysis'
import { recommendation as submitRecommendationApi } from '@/api/analysis'

const analysis = useAnalysisStore()
const loading = ref(false)

const allFields = computed<string[]>(() => {
  const r = analysis.profileResult
  if (!r || !Array.isArray(r)) return []
  return (r as { field: string; min?: number; max?: number }[]).map((x) => x.field)
})

interface ParamControl {
  value: number
  min: number
  max: number
}

const knownParams = computed<Record<string, { min: number; max: number }>>(() => {
  const r = analysis.profileResult
  if (!r || !Array.isArray(r)) return {}
  const result: Record<string, { min: number; max: number }> = {}
  for (const entry of r as { field: string; min?: number; max?: number }[]) {
    if (entry.min !== null && entry.max !== null) {
      result[entry.field] = { min: entry.min!, max: entry.max! }
    }
  }
  return result
})

const form = reactive({
  targetField: '',
  targetValue: 90,
  params: {} as Record<string, ParamControl>,
})

watchEffect(() => {
  const kp = knownParams.value
  const current = form.params
  for (const [k, v] of Object.entries(kp)) {
    if (!current[k]) {
      current[k] = { value: (v.min + v.max) / 2, min: v.min, max: v.max }
    } else {
      current[k].min = v.min
      current[k].max = v.max
      current[k].value = Math.max(v.min, Math.min(v.max, current[k].value))
    }
  }
  for (const k of Object.keys(current)) {
    if (!kp[k]) delete current[k]
  }
})

async function handleSubmit() {
  loading.value = true
  try {
    const result = await submitRecommendationApi({
      feature_fields: Object.keys(form.params),
      target_field: form.targetField,
      target_value: form.targetValue,
      constraints: Object.entries(form.params).map(([field, c]) => ({
        field,
        min: c.min,
        max: c.max,
      })),
    })
    analysis.recommendationResult = result as any
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.recommendation-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.param-value {
  margin-left: 12px;
  min-width: 40px;
  display: inline-block;
  font-family: 'Fira Code', monospace;
  font-weight: 500;
}
.result-card {
  margin-top: 16px;
}
.recommend-params {
  margin-top: 12px;
}
.recommend-params h4,
.risk-notes h4 {
  font-size: 13px;
  font-weight: 500;
  margin: 0 0 8px;
}
.rec-row {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  border-bottom: 1px solid var(--el-border-color-light);
  font-size: 13px;
}
.rec-name {
  font-family: 'Fira Code', monospace;
  color: var(--el-color-primary);
}
.rec-value {
  font-family: 'Fira Code', monospace;
  font-weight: 500;
}
.risk-notes {
  margin-top: 12px;
}
.risk-note {
  font-size: 12px;
  color: var(--el-color-warning);
  margin: 4px 0;
}
</style>

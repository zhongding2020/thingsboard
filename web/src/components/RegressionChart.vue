<template>
  <div class="regression-panel">
    <el-form inline class="regression-form">
      <el-form-item label="特征参数">
        <el-select v-model="featureFields" multiple :disabled="!allFields.length" style="width: 240px">
          <el-option v-for="f in allFields" :key="f" :label="f" :value="f" />
        </el-select>
      </el-form-item>
      <el-form-item label="目标结果">
        <el-select v-model="targetField" :disabled="!allFields.length" style="width: 180px">
          <el-option v-for="f in allFields" :key="f" :label="f" :value="f" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleCompute" :loading="loading">计算</el-button>
      </el-form-item>
    </el-form>
    <div class="chart-wrapper">
      <div v-if="result" class="regression-result">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="R²">{{ result.r_squared.toFixed(4) }}</el-descriptions-item>
          <el-descriptions-item label="RMSE">{{ result.rmse.toFixed(4) }}</el-descriptions-item>
          <el-descriptions-item label="模型">{{ result.model_type }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="result.coefficients" class="regression-coeff">
          <h4>Coefficients</h4>
          <div v-for="(v, k) in result.coefficients" :key="k" class="coeff-row">
            <span class="coeff-name">{{ k }}</span>
            <span class="coeff-value">{{ v.toFixed(4) }}</span>
          </div>
        </div>
      </div>
      <el-empty v-else description="选择参数后点击计算" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useAnalysisStore } from '@/stores/analysis'
import { regression } from '@/api/analysis'

const analysis = useAnalysisStore()
const loading = ref(false)
const result = ref<{ r_squared: number; rmse: number; coefficients: Record<string, number>; model_type: string } | null>(null)

const featureFields = ref<string[]>([])
const targetField = ref('')

const allFields = computed<string[]>(() => {
  const r = analysis.profileResult
  if (!r || !Array.isArray(r)) return []
  return (r as { field: string }[]).map((x) => x.field)
})

async function handleCompute() {
  if (!featureFields.value.length || !targetField.value) return
  loading.value = true
  try {
    result.value = await regression({
      feature_fields: featureFields.value,
      target_field: targetField.value,
      model_type: 'linear',
    }) as { r_squared: number; rmse: number; coefficients: Record<string, number>; model_type: string }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.regression-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.regression-form {
  margin: 0;
}
.chart-wrapper {
  min-height: 200px;
}
.regression-result {
  max-width: 500px;
}
.regression-coeff {
  margin-top: 16px;
}
.regression-coeff h4 {
  font-size: 13px;
  font-weight: 500;
  margin: 0 0 8px;
}
.coeff-row {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  border-bottom: 1px solid var(--el-border-color-light);
  font-size: 13px;
}
.coeff-name {
  font-family: 'Fira Code', monospace;
  color: var(--el-color-primary);
}
.coeff-value {
  font-family: 'Fira Code', monospace;
  font-weight: 500;
}
</style>

<template>
  <div class="excel-rec">
    <el-card shadow="hover">
      <template #header>参数推荐</template>
      <el-form label-width="120px">
        <el-form-item label="目标结果">
          <el-select v-model="targetField" style="width: 200px">
            <el-option v-for="f in allFields" :key="f" :label="f" :value="f" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标值">
          <el-input-number v-model="targetValue" :min="0" :max="9999" :step="0.1" />
        </el-form-item>
        <el-form-item v-for="f in featureFields" :key="f" :label="f">
          <el-slider v-model="params[f]" :min="0" :max="500" :step="0.1" style="width: 300px" />
          <span class="val">{{ params[f].toFixed(1) }}</span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSubmit" :loading="loading">提交推荐</el-button>
        </el-form-item>
      </el-form>
    </el-card>
    <el-card v-if="result" shadow="hover" class="result-card">
      <template #header>推荐结果</template>
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="预期目标值">{{ result.predicted_target.toFixed(4) }}</el-descriptions-item>
      </el-descriptions>
      <div class="rec-params">
        <h4>推荐参数</h4>
        <div v-for="(v, k) in result.recommended_parameters" :key="k" class="rec-row">
          <span class="rec-name">{{ k }}</span>
          <span class="rec-value">{{ v.toFixed(1) }}</span>
        </div>
      </div>
      <div v-if="result.risk_notes.length" class="risks">
        <h4>风险提示</h4>
        <p v-for="(n, i) in result.risk_notes" :key="i" class="risk-note">{{ n }}</p>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { excelRecommendation } from '@/api/analysis'

const props = defineProps<{ datasetId: string; fields: { features: string[]; targets: string[] } }>()

const loading = ref(false)
const result = ref<any>(null)
const targetField = ref('')
const targetValue = ref(90)
const params = reactive<Record<string, number>>({})

const allFields = computed(() => [...props.fields.features, ...props.fields.targets])
const featureFields = computed(() => props.fields.features)

async function handleSubmit() {
  if (!targetField.value) return
  loading.value = true
  try {
    result.value = await excelRecommendation(props.datasetId, {
      feature_fields: featureFields.value,
      target_field: targetField.value,
      target_value: targetValue.value,
      constraints: featureFields.value.map((f) => ({ field: f, min: 0, max: 500 })),
    })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.excel-rec { display: flex; flex-direction: column; gap: 16px; }
.val { margin-left: 12px; min-width: 40px; display: inline-block; font-family: 'Fira Code', monospace; font-weight: 500; }
.result-card { margin-top: 16px; }
.rec-params { margin-top: 12px; }
.rec-params h4, .risks h4 { font-size: 13px; font-weight: 500; margin: 0 0 8px; }
.rec-row { display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid var(--el-border-color-light); font-size: 13px; }
.rec-name { font-family: 'Fira Code', monospace; color: var(--el-color-primary); }
.rec-value { font-family: 'Fira Code', monospace; font-weight: 500; }
.risks { margin-top: 12px; }
.risk-note { font-size: 12px; color: var(--el-color-warning); margin: 4px 0; }
</style>

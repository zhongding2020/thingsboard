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
    <div class="chart-wrapper">
      <div v-if="results.length" class="correlation-results">
        <div v-for="r in results" :key="r.field_x + '|' + r.field_y" class="correlation-card">
          <div class="correlation-pair">{{ r.field_x }} × {{ r.field_y }}</div>
          <div class="correlation-stats">
            <span>r = {{ r.coefficient.toFixed(4) }}</span>
            <span>p = {{ r.p_value.toFixed(4) }}</span>
          </div>
          <el-progress
            :percentage="Math.abs(r.coefficient) * 100"
            :color="r.coefficient > 0 ? '#3b82f6' : '#ef4444'"
            :stroke-width="8"
          />
        </div>
      </div>
      <el-empty v-else description="选择参数后点击计算" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { correlation } from '@/api/analysis'

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

const allFields = computed(() => [...props.featureFields, ...props.targetFields])

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
    results.value = await correlation({
      dataset_id: props.datasetId,
      method: 'pearson',
    }) as unknown as { field_x: string; field_y: string; coefficient: number; p_value: number; method: string }[]
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.correlation-form { margin-bottom: 12px; }
.chart-wrapper { min-height: 120px; }
.correlation-results { display: flex; flex-direction: column; gap: 10px; }
.correlation-card {
  background: var(--el-bg-color);
  border-radius: 6px;
  padding: 10px 14px;
  border: 1px solid var(--el-border-color-light);
}
.correlation-pair {
  font-family: 'Fira Code', monospace;
  font-size: 13px;
  font-weight: 500;
  color: var(--el-color-primary);
  margin-bottom: 4px;
}
.correlation-stats {
  display: flex;
  gap: 16px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
}
</style>

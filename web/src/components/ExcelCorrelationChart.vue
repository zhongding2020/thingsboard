<template>
  <div class="correlation-panel">
    <el-form inline>
      <el-form-item label="参数 X">
        <el-select v-model="fieldX" :disabled="!paramFields.length" style="width: 180px">
          <el-option v-for="f in paramFields" :key="f" :label="f" :value="f" />
        </el-select>
      </el-form-item>
      <el-form-item label="参数 Y">
        <el-select v-model="fieldY" :disabled="!paramFields.length" style="width: 180px">
          <el-option v-for="f in paramFields" :key="f" :label="f" :value="f" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleCompute" :loading="loading">计算</el-button>
      </el-form-item>
    </el-form>
    <div v-if="result" class="correlation-result">
      <el-descriptions :column="3" border size="small">
        <el-descriptions-item label="系数">{{ result.coefficient.toFixed(4) }}</el-descriptions-item>
        <el-descriptions-item label="P 值">{{ result.p_value.toFixed(4) }}</el-descriptions-item>
        <el-descriptions-item label="方法">{{ result.method }}</el-descriptions-item>
      </el-descriptions>
    </div>
    <el-empty v-else description="选择参数后点击计算" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { excelCorrelation } from '@/api/analysis'

const props = defineProps<{ datasetId: string; fields: { features: string[]; targets: string[] } }>()

const loading = ref(false)
const fieldX = ref('')
const fieldY = ref('')
const result = ref<{ coefficient: number; p_value: number; method: string } | null>(null)

const paramFields = computed(() => [...props.fields.features, ...props.fields.targets])

async function handleCompute() {
  if (!fieldX.value || !fieldY.value) return
  loading.value = true
  try {
    result.value = await excelCorrelation(props.datasetId, {
      field_x: fieldX.value, field_y: fieldY.value, method: 'pearson',
    }) as any
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.correlation-panel { display: flex; flex-direction: column; gap: 12px; }
.correlation-result { max-width: 500px; }
</style>

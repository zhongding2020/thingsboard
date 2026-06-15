<template>
  <el-dialog v-model="visible" title="设备参数" width="600px" :close-on-click-modal="false" @closed="handleClose">
    <template v-if="paramData">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="设备">{{ deviceId }}</el-descriptions-item>
        <el-descriptions-item label="参数集">{{ paramData.parameter_set.name }} v{{ paramData.parameter_set.version }}</el-descriptions-item>
        <el-descriptions-item label="设备类型">{{ paramData.parameter_set.device_type }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <ParameterStatus :status="paramData.parameter_set.status" />
        </el-descriptions-item>
      </el-descriptions>

      <h4 class="items-title">参数项</h4>
      <el-table :data="paramData.items" stripe size="small" max-height="320">
        <el-table-column prop="param_key" label="参数名" min-width="120" />
        <el-table-column label="值" width="110">
          <template #default="{ row }">{{ formatValue(row.param_value, row.data_type) }}</template>
        </el-table-column>
        <el-table-column prop="unit" label="单位" width="60" />
        <el-table-column label="规格" width="130">
          <template #default="{ row }">
            <span class="spec-range">{{ row.min_value ?? '∞' }} ~ {{ row.max_value ?? '∞' }}</span>
          </template>
        </el-table-column>
      </el-table>

      <div class="param-actions">
        <el-button type="primary" @click="handleFetch" :loading="loading">拉取最新参数</el-button>
        <el-button type="success" @click="handleApply" :disabled="!fetchedSetId">确认已应用</el-button>
        <el-tag v-if="msg" :type="msgType" size="small">{{ msg }}</el-tag>
      </div>
    </template>
    <el-empty v-else-if="!loading" description="该设备类型暂无活跃参数集" />
    <div v-else v-loading="loading" class="loading-wrap" />
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { getLatest, recordConfirmation, type ParameterSetWithItems } from '@/api/parameters'
import { useSessionStore } from '@/stores/session'
import ParameterStatus from './ParameterStatus.vue'

const session = useSessionStore()

const props = defineProps<{
  modelValue: boolean
  deviceId: string
  deviceType: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const visible = ref(false)
const loading = ref(false)
const paramData = ref<ParameterSetWithItems | null>(null)
const fetchedSetId = ref<number | null>(null)
const msg = ref('')
const msgType = ref<'success' | 'danger' | 'warning' | 'info'>('info')

watch(() => props.modelValue, (v) => {
  visible.value = v
  if (v) loadParams()
})

watch(visible, (v) => {
  if (!v) emit('update:modelValue', v)
})

function formatValue(value: unknown, dataType: string): string {
  if (value === null || value === undefined) return '—'
  if (dataType === 'float' || dataType === 'double') {
    const n = Number(value)
    return isNaN(n) ? String(value) : n.toFixed(4)
  }
  return String(value)
}

async function loadParams() {
  loading.value = true
  paramData.value = null
  fetchedSetId.value = null
  msg.value = ''
  try {
    const data = await getLatest(props.deviceType)
    paramData.value = data
    fetchedSetId.value = data.parameter_set.id
    msg.value = '已获取最新参数'
    msgType.value = 'success'
  } catch {
    msg.value = '无活跃参数'
    msgType.value = 'warning'
  } finally {
    loading.value = false
  }
}

async function handleFetch() {
  loading.value = true
  msg.value = ''
  try {
    const data = await getLatest(props.deviceType)
    paramData.value = data
    fetchedSetId.value = data.parameter_set.id
    msg.value = '已获取最新参数'
    msgType.value = 'success'
  } catch {
    msg.value = '拉取失败'
    msgType.value = 'danger'
  } finally {
    loading.value = false
  }
}

async function handleApply() {
  if (!fetchedSetId.value || !paramData.value) return
  loading.value = true
  msg.value = ''
  try {
    await recordConfirmation({
      device_id: props.deviceId,
      device_type: props.deviceType,
      parameter_set_id: paramData.value.parameter_set.id,
      parameter_version: paramData.value.parameter_set.version,
      status: 'applied',
      message: `Applied by ${session.currentUser || 'operator'}`,
    })
    msg.value = '已确认应用'
    msgType.value = 'success'
  } catch {
    msg.value = '确认失败'
    msgType.value = 'danger'
  } finally {
    loading.value = false
  }
}

function handleClose() {
  paramData.value = null
  fetchedSetId.value = null
  msg.value = ''
}
</script>

<style scoped>
.items-title {
  font-size: 14px;
  font-weight: 600;
  margin: 16px 0 8px;
}
.spec-range {
  font-family: 'Fira Code', monospace;
  font-size: 12px;
  color: var(--el-text-color-regular);
}
.param-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
}
.loading-wrap {
  min-height: 120px;
}
</style>

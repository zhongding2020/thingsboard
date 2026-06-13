<template>
  <el-card shadow="hover" class="analysis-filter">
    <el-form :model="form" inline>
      <el-form-item label="设备">
        <el-select v-model="form.deviceId" placeholder="选择设备" clearable @change="onDeviceChange">
          <el-option v-for="d in devices" :key="d" :label="d" :value="d" />
        </el-select>
      </el-form-item>
      <el-form-item label="时间范围">
        <el-date-picker
          v-model="dateRange"
          type="datetimerange"
          range-separator="至"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          :shortcuts="timeShortcuts"
        />
      </el-form-item>
      <el-form-item label="参数">
        <el-select v-model="form.featureFields" multiple placeholder="选择参数" style="width: 240px">
          <el-option v-for="f in availableFields.params" :key="f" :label="f" :value="f" />
        </el-select>
      </el-form-item>
      <el-form-item label="结果">
        <el-select v-model="form.targetFields" multiple placeholder="选择结果" style="width: 200px">
          <el-option v-for="f in availableFields.results" :key="f" :label="f" :value="f" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch" :loading="loading">查询</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useAnalysisStore, type AnalysisFilter } from '@/stores/analysis'
import { profile } from '@/api/analysis'
import { listDevices as fetchDevices } from '@/api/records'

const analysis = useAnalysisStore()
const loading = ref(false)
const devices = ref<string[]>([])
const dateRange = ref<[Date, Date] | null>([new Date(Date.now() - 604800000), new Date()])

const timeShortcuts = [
  { text: '近一天', value: () => [new Date(Date.now() - 86400000), new Date()] },
  { text: '最近一周', value: () => [new Date(Date.now() - 604800000), new Date()] },
  { text: '一个月', value: () => [new Date(Date.now() - 2592000000), new Date()] },
]

const FIELD_MAP: Record<string, { params: string[]; results: string[] }> = {
  'reflow-oven': {
    params: ['temperature', 'conveyor_speed', 'oxygen_ppm'],
    results: ['solder_joint_quality', 'voiding_pct'],
  },
  'injection-molder': {
    params: ['melt_temp', 'injection_pressure', 'cooling_time'],
    results: ['dimensional_accuracy', 'flash_present'],
  },
}

const availableFields = reactive<{ params: string[]; results: string[] }>({
  params: [],
  results: [],
})

const form = reactive({
  deviceId: '',
  featureFields: [] as string[],
  targetFields: [] as string[],
})

function onDeviceChange() {
  const fields = FIELD_MAP[form.deviceId]
  if (fields) {
    availableFields.params = fields.params
    availableFields.results = fields.results
    form.featureFields = []
    form.targetFields = []
  } else {
    availableFields.params = []
    availableFields.results = []
  }
}

async function handleSearch() {
  if (!form.featureFields.length || !form.targetFields.length) return
  loading.value = true
  try {
    const params: Partial<AnalysisFilter> = {}
    if (form.deviceId) params.deviceId = form.deviceId
    if (dateRange.value) {
      params.timeRange = [dateRange.value[0].toISOString(), dateRange.value[1].toISOString()]
    }

    const [profileResult] = await Promise.all([
      profile({
        feature_fields: form.featureFields,
        target_fields: form.targetFields,
      }),
    ])
    analysis.profileResult = profileResult as Record<string, Record<string, unknown>>
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    devices.value = await fetchDevices()
    if (devices.value.length && !form.deviceId) {
      form.deviceId = devices.value[0]
      onDeviceChange()
    }
  } catch {
    // Silently fail
  }
})
</script>

<style scoped>
.analysis-filter {
  margin-bottom: 16px;
}
</style>

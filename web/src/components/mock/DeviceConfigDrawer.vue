<template>
  <el-drawer v-model="visible" title="参数配置" size="400px">
    <template v-if="device">
      <div class="config-device-info">
        <span class="config-device-name">{{ device.name || device.device_id }}</span>
        <el-tag size="small">{{ device.status }}</el-tag>
      </div>
      <el-form v-if="paramEntries.length" label-width="140px" size="default" class="config-form">
        <el-form-item v-for="p in paramEntries" :key="p.key" :label="p.key">
          <el-input-number
            v-model="p.value"
            :min="p.min"
            :max="p.max"
            :step="p.step"
            controls-position="right"
            style="width:100%"
          />
          <span v-if="p.unit" class="param-unit">{{ p.unit }}</span>
        </el-form-item>
      </el-form>
      <el-empty v-else description="该设备类型没有可配置参数" />
      <div class="config-actions" v-if="paramEntries.length">
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveParams">保存</el-button>
      </div>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps<{ visible: boolean; device: any }>()
const emit = defineEmits(['update:visible', 'updated'])

const visible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

const saving = ref(false)

// Derive editable params from device.current_params with range info from DEVICE_TEMPLATES
// Use default ranges (hardcoded for the 5 mechanism types, fallback for others)
const RANGES: Record<string, Record<string, { min: number; max: number; step: number; unit: string }>> = {
  'reflow-oven': {
    temperature: { min: 100, max: 300, step: 1, unit: '°C' },
    conveyor_speed: { min: 10, max: 100, step: 1, unit: 'mm/s' },
    oxygen_ppm: { min: 0, max: 1000, step: 1, unit: 'ppm' },
  },
  'injection-molder': {
    melt_temp: { min: 150, max: 350, step: 1, unit: '°C' },
    injection_pressure: { min: 50, max: 200, step: 1, unit: 'MPa' },
    cooling_time: { min: 5, max: 60, step: 1, unit: 's' },
  },
  'oven-curing': {
    oven_temp: { min: 80, max: 200, step: 1, unit: '°C' },
    cure_duration_min: { min: 10, max: 120, step: 1, unit: 'min' },
    humidity_pct: { min: 10, max: 80, step: 1, unit: '%' },
    airflow_rate: { min: 5, max: 50, step: 1, unit: 'm³/h' },
  },
  'cnc-drill': {
    spindle_speed: { min: 5000, max: 25000, step: 100, unit: 'RPM' },
    feed_rate: { min: 100, max: 800, step: 10, unit: 'mm/min' },
    drill_depth: { min: 0.5, max: 12, step: 0.1, unit: 'mm' },
    coolant_flow: { min: 2, max: 15, step: 0.5, unit: 'L/min' },
  },
  'coating-machine': {
    spray_pressure: { min: 10, max: 60, step: 1, unit: 'psi' },
    coating_thickness_um: { min: 5, max: 100, step: 1, unit: 'μm' },
    cure_temp: { min: 60, max: 180, step: 1, unit: '°C' },
    conveyor_speed: { min: 0.5, max: 5.0, step: 0.1, unit: 'm/min' },
  },
}

interface ParamEntry { key: string; value: number; min: number; max: number; step: number; unit: string }

const paramEntries = computed<ParamEntry[]>(() => {
  if (!props.device?.current_params) return []
  const params = props.device.current_params
  const ranges = RANGES[props.device.device_type] || {}
  return Object.entries(params)
    .filter(([, v]) => typeof v === 'number')
    .map(([key, value]) => {
      const range = ranges[key] || { min: 0, max: (value as number) * 2 || 100, step: 1, unit: '' }
      return { key, value: value as number, ...range }
    })
})

async function saveParams() {
  if (!props.device) return
  saving.value = true
  try {
    const body: Record<string, number> = {}
    paramEntries.value.forEach(p => { body[p.key] = p.value })
    const r = await fetch(`/api/v1/mock/devices/${props.device.device_id}/params`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!r.ok) throw new Error('Save failed')
    ElMessage.success('参数已更新')
    emit('updated')
    visible.value = false
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.config-device-info { display: flex; align-items: center; gap: 8px; margin-bottom: 20px; }
.config-device-name { font-weight: 600; }
.config-form { margin-bottom: 20px; }
.param-unit { margin-left: 8px; font-size: 12px; color: var(--el-text-color-secondary); }
.config-actions { display: flex; justify-content: flex-end; gap: 8px; }
</style>

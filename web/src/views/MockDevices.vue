<template>
  <div class="mock-devices-page">
    <div class="page-header">
      <h2 class="page-title">工艺装备模拟器</h2>
      <el-button type="primary" @click="showAddDialog = true">+ 添加设备</el-button>
    </div>

    <!-- 概览条 -->
    <div class="summary-bar">
      <span class="summary-item running">&#x1F7E2; 运行中: {{ summary.running }}</span>
      <span class="summary-item paused">&#x1F7E1; 暂停: {{ summary.paused }}</span>
      <span class="summary-item idle">&#x26AA; 空闲: {{ summary.idle }}</span>
    </div>

    <!-- 设备卡片网格 -->
    <div v-if="devices.length" class="device-grid">
      <DeviceCard
        v-for="d in devices"
        :key="d.device_id"
        :device="d"
        @configure="openConfig"
        @experiment="openExperiment"
        @log="openLog"
        @start="handleStart(d.device_id)"
        @pause="handlePause(d.device_id)"
        @stop="handleStop(d.device_id)"
        @delete="handleDelete(d.device_id)"
      />
    </div>
    <el-empty v-else description="暂无模拟设备，点击右上角「添加设备」创建" />

    <!-- 添加设备弹窗 -->
    <AddDeviceDialog
      v-model:visible="showAddDialog"
      @created="fetchDevices"
    />

    <!-- 参数配置抽屉 -->
    <DeviceConfigDrawer
      v-model:visible="configDrawer.visible"
      :device="configDrawer.device"
      @updated="fetchDevices"
    />

    <!-- 实验面板抽屉 -->
    <ExperimentPanel
      v-model:visible="experimentDrawer.visible"
      :device="experimentDrawer.device"
    />

    <!-- 设备日志抽屉 -->
    <DeviceLogDrawer
      v-model:visible="logDrawer.visible"
      :device="logDrawer.device"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import DeviceCard from '@/components/mock/DeviceCard.vue'
import AddDeviceDialog from '@/components/mock/AddDeviceDialog.vue'
import DeviceConfigDrawer from '@/components/mock/DeviceConfigDrawer.vue'
import ExperimentPanel from '@/components/mock/ExperimentPanel.vue'
import DeviceLogDrawer from '@/components/mock/DeviceLogDrawer.vue'

interface MockDevice {
  device_id: string
  device_type: string
  name: string
  line_id: string
  line_name: string
  status: string
  report_count: number
  report_interval: number
  current_params: Record<string, any>
  last_heartbeat?: number
}

const devices = ref<MockDevice[]>([])
const summary = reactive({ running: 0, paused: 0, idle: 0 })
const showAddDialog = ref(false)

const configDrawer = reactive<{ visible: boolean; device: MockDevice | null }>({
  visible: false, device: null,
})
const experimentDrawer = reactive<{ visible: boolean; device: MockDevice | null }>({
  visible: false, device: null,
})
const logDrawer = reactive<{ visible: boolean; device: MockDevice | null }>({
  visible: false, device: null,
})

async function fetchDevices() {
  try {
    const r = await fetch('/api/v1/mock/devices')
    if (!r.ok) return
    const data = await r.json()
    devices.value = data.devices || []
    summary.running = data.summary?.running ?? 0
    summary.paused = data.summary?.paused ?? 0
    summary.idle = data.summary?.idle ?? 0
  } catch { /* ignore */ }
}

async function handleStart(id: string) {
  await fetch(`/api/v1/mock/devices/${id}/start`, { method: 'POST' })
  fetchDevices()
}
async function handlePause(id: string) {
  await fetch(`/api/v1/mock/devices/${id}/pause`, { method: 'POST' })
  fetchDevices()
}
async function handleStop(id: string) {
  await fetch(`/api/v1/mock/devices/${id}/stop`, { method: 'POST' })
  fetchDevices()
}
async function handleDelete(id: string) {
  try {
    await ElMessageBox.confirm('删除后历史数据保留。确认删除？', '确认删除', { type: 'warning' })
    await fetch(`/api/v1/mock/devices/${id}`, { method: 'DELETE' })
    ElMessage.success('已删除')
    fetchDevices()
  } catch { /* cancelled */ }
}

function openConfig(d: MockDevice) {
  configDrawer.device = d
  configDrawer.visible = true
}
function openExperiment(d: MockDevice) {
  experimentDrawer.device = d
  experimentDrawer.visible = true
}
function openLog(d: MockDevice) {
  logDrawer.device = d
  logDrawer.visible = true
}

let timer: number | undefined
onMounted(() => {
  fetchDevices()
  timer = window.setInterval(fetchDevices, 5000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.mock-devices-page {
  max-width: 1200px;
  margin: 0 auto;
}
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.page-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0;
}
.summary-bar {
  display: flex;
  gap: 20px;
  padding: 10px 16px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 13px;
}
.summary-item.running { color: #67c23a; }
.summary-item.paused { color: #e6a23c; }
.summary-item.idle { color: #909399; }
.device-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 14px;
}
</style>

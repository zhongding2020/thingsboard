<template>
  <el-drawer v-model="visible" :title="`设备日志 — ${device?.name || device?.device_id || ''}`" size="500px" @close="close">
    <template v-if="device">
      <div class="log-toolbar">
        <el-button size="small" @click="clearLogs">清空</el-button>
        <el-switch
          v-model="autoScroll"
          active-text="自动滚动"
          size="small"
          style="margin-left: auto"
        />
      </div>
      <div ref="logContainer" class="log-container">
        <div v-if="logs.length === 0 && !connected" class="log-empty">
          <el-icon class="is-loading" :size="20"><Loading /></el-icon>
          <span>正在连接...</span>
        </div>
        <div v-else-if="logs.length === 0" class="log-empty">暂无日志</div>
        <div
          v-for="(entry, i) in logs"
          :key="i"
          class="log-entry"
          :class="`log-${entry.eventType}`"
        >
          <span class="log-time">{{ entry.time }}</span>
          <span class="log-badge">{{ entry.badge }}</span>
          <span class="log-msg">{{ entry.message }}</span>
        </div>
      </div>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { Loading } from '@element-plus/icons-vue'

const props = defineProps<{ device: any }>()
const visible = defineModel<boolean>('visible', { default: false })

interface LogEntry {
  time: string
  eventType: string
  badge: string
  message: string
}

const logs = ref<LogEntry[]>([])
const autoScroll = ref(true)
const connected = ref(false)
const logContainer = ref<HTMLElement>()
let eventSource: EventSource | null = null

const EVENT_BADGES: Record<string, string> = {
  heartbeat: '💓 心跳',
  'data.reported': '📊 上报',
  'experiment.progress': '🧪 实验',
  'experiment.complete': '✅ 完成',
  status: '📌 状态',
  error: '❌ 错误',
}

function formatTime(): string {
  const now = new Date()
  return now.toLocaleTimeString('zh-CN', { hour12: false })
}

function addLog(eventType: string, data: Record<string, any>) {
  const badge = EVENT_BADGES[eventType] || eventType
  let message = ''

  switch (eventType) {
    case 'heartbeat':
      message = `状态: ${data.status || '-'}；参数: ${JSON.stringify(data.current_params || {})}`
      break
    case 'data.reported':
      message = `条码: ${data.barcode || '-'}`
      break
    case 'experiment.progress':
      message = `计划 #${data.plan_id}：第 ${data.run_order}/${data.total_runs} 轮`
      break
    case 'experiment.complete':
      message = `计划 #${data.plan_id} 全部完成，共 ${data.total_runs} 轮`
      break
    case 'status':
      message = `切换为: ${data.status || '-'}`
      break
    case 'error':
      message = data.message || '未知错误'
      break
    default:
      message = JSON.stringify(data)
  }

  logs.value.push({ time: formatTime(), eventType, badge, message })
}

function scrollToBottom() {
  if (!autoScroll.value) return
  nextTick(() => {
    const el = logContainer.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

function clearLogs() {
  logs.value = []
}

function connect() {
  if (!props.device?.device_id) return
  const deviceId = props.device.device_id
  const url = `/api/v1/mock/devices/${encodeURIComponent(deviceId)}/events`

  eventSource = new EventSource(url)

  eventSource.onopen = () => {
    connected.value = true
  }

  // SSE events are dispatched by event type; fallback to onmessage for unnamed events
  const eventTypes = ['status', 'heartbeat', 'data.reported', 'experiment.progress', 'experiment.complete', 'error']
  for (const type of eventTypes) {
    eventSource.addEventListener(type, (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data)
        addLog(type, data)
        scrollToBottom()
      } catch { /* ignore malformed events */ }
    })
  }

  eventSource.onerror = () => {
    connected.value = false
    // EventSource auto-reconnects; log the transient disconnect
    addLog('status', { status: 'disconnected' })
  }
}

function close() {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
  connected.value = false
}

watch(() => props.device, (d) => {
  if (d && visible.value) {
    connect()
  }
})

watch(visible, (v) => {
  if (v && props.device) {
    // Clear old logs when opening for a device
    logs.value = []
    connect()
  }
})
</script>

<style scoped>
.log-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--el-border-color-light);
}

.log-container {
  height: calc(100vh - 180px);
  overflow-y: auto;
  font-family: 'SF Mono', 'Menlo', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.6;
}

.log-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 80px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.log-entry {
  display: flex;
  gap: 8px;
  padding: 3px 0;
  border-bottom: 1px solid var(--el-border-color-extra-light);
  align-items: flex-start;
}

.log-time {
  color: var(--el-text-color-disabled);
  flex-shrink: 0;
  font-size: 11px;
  min-width: 72px;
}

.log-badge {
  flex-shrink: 0;
  font-size: 11px;
  min-width: 64px;
}

.log-msg {
  color: var(--el-text-color-regular);
  word-break: break-all;
}

.log-error .log-badge { color: var(--el-color-danger); }
.log-error .log-msg { color: var(--el-color-danger); }
.log-experiment\.complete .log-badge { color: var(--el-color-success); }
</style>

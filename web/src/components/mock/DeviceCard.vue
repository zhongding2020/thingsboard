<template>
  <div class="device-card" :class="`status-${device.status}`">
    <div class="card-header">
      <span class="status-dot" :class="device.status" />
      <span class="device-id">{{ device.device_id }}</span>
      <span class="device-type">{{ typeLabel }}</span>
      <el-popconfirm title="确认删除？" @confirm="$emit('delete')">
        <template #reference>
          <el-button text size="small" type="danger" class="delete-btn">删除</el-button>
        </template>
      </el-popconfirm>
    </div>
    <div class="card-body">
      <div class="info-row"><span class="label">工艺</span><span>{{ typeLabel }}</span></div>
      <div class="info-row"><span class="label">产线</span><span>{{ device.line_name || device.line_id }}</span></div>
      <div class="info-row"><span class="label">状态</span><span>{{ statusLabel }}</span></div>
      <div class="info-row"><span class="label">上报</span><span>{{ device.report_count }} 条</span></div>
    </div>
    <div class="card-footer">
      <el-button size="small" @click="$emit('configure', device)">参数配置</el-button>
      <el-button size="small" @click="$emit('experiment', device)">实验</el-button>
      <template v-if="device.status === 'running'">
        <el-button size="small" type="warning" @click="$emit('pause')">暂停</el-button>
        <el-button size="small" type="danger" @click="$emit('stop')">停止</el-button>
      </template>
      <template v-else-if="device.status === 'paused'">
        <el-button size="small" type="success" @click="$emit('start')">恢复</el-button>
        <el-button size="small" type="danger" @click="$emit('stop')">停止</el-button>
      </template>
      <el-button v-else size="small" type="primary" @click="$emit('start')">启动</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ device: any }>()
defineEmits(['configure', 'experiment', 'start', 'pause', 'stop', 'delete'])

const TYPE_LABELS: Record<string, string> = {
  'reflow-oven': '回流焊',
  'injection-molder': '注塑成型',
  'oven-curing': '固化炉',
  'cnc-drill': 'CNC钻孔',
  'coating-machine': '涂覆机',
  'pick-and-place': '贴片',
  'wave-solder': '波峰焊',
  '3d-printer': '3D打印',
  'testing-station': '测试站',
  'laser-cutter': '激光切割',
  'xray-inspection': 'X-Ray检测',
  'wire-bonder': '键合',
  'ultrasonic-cleaner': '超声清洗',
}
const STATUS_LABELS: Record<string, string> = {
  idle: '空闲', running: '运行中', paused: '已暂停',
}

const typeLabel = computed(() => TYPE_LABELS[props.device.device_type] || props.device.device_type)
const statusLabel = computed(() => STATUS_LABELS[props.device.status] || props.device.status)
</script>

<style scoped>
.device-card {
  border: 1px solid var(--el-border-color);
  border-radius: 10px;
  padding: 14px;
  background: var(--el-bg-color);
  transition: box-shadow 0.2s;
}
.device-card:hover { box-shadow: 0 2px 10px rgba(0,0,0,0.06); }
.device-card.status-running { border-left: 3px solid #67c23a; }
.device-card.status-paused { border-left: 3px solid #e6a23c; }
.device-card.status-idle { border-left: 3px solid #909399; }

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.status-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
}
.status-dot.running { background: #67c23a; }
.status-dot.paused { background: #e6a23c; }
.status-dot.idle { background: #909399; }
.device-id { font-weight: 600; font-size: 14px; flex: 1; }
.device-type { font-size: 11px; color: var(--el-text-color-secondary); background: var(--el-fill-color-light); padding: 1px 6px; border-radius: 4px; }
.delete-btn { margin-left: auto; }

.card-body { margin-bottom: 10px; }
.info-row { display: flex; justify-content: space-between; font-size: 12px; padding: 2px 0; color: var(--el-text-color-regular); }
.info-row .label { color: var(--el-text-color-secondary); }

.card-footer { display: flex; gap: 6px; flex-wrap: wrap; }
</style>

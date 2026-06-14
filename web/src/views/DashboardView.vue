<template>
  <div class="dashboard">
    <div class="dashboard-header">
      <h2 class="page-title">仪表盘</h2>
      <p class="page-desc">实时工艺参数监控概览</p>
    </div>
    <el-row :gutter="16">
      <el-col :span="6" v-for="(card, index) in cards" :key="card.label">
        <div
          class="stat-card"
          :style="{ '--i': index, '--accent': card.accent }"
        >
          <div class="stat-card-header">
            <el-icon :size="20" :style="{ color: card.accent }"><component :is="card.icon" /></el-icon>
            <span>{{ card.label }}</span>
          </div>
          <div class="stat-card-value">
            <span class="stat-number" ref="statRefs">{{ card.value }}</span>
            <span class="stat-unit" v-if="card.unit">{{ card.unit }}</span>
          </div>
          <div class="stat-card-footer">{{ card.footer }}</div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="dashboard-secondary">
      <el-col :span="14">
        <el-card class="section-card">
          <template #header>
            <div class="section-header">
              <span>最近数据</span>
              <el-button text size="small" @click="$router.push('/data')">查看全部</el-button>
            </div>
          </template>
          <div v-if="latestRecords.length" class="record-list">
            <div
              v-for="(rec, i) in latestRecords"
              :key="rec.barcode"
              class="record-row"
              :style="{ '--i': i }"
            >
              <span class="record-barcode">{{ rec.barcode }}</span>
              <span class="record-device">{{ rec.device_id }}</span>
              <span class="record-time">{{ formatTime(rec.processed_at) }}</span>
            </div>
          </div>
          <el-empty v-else description="暂无数据" :image-size="80" />
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card class="section-card">
          <template #header>
            <div class="section-header">
              <span>系统资源</span>
            </div>
          </template>
          <div class="resource-list">
            <div class="resource-item">
              <div class="resource-label">
                <span>CPU</span>
                <span>{{ system.resources.cpu }}%</span>
              </div>
              <el-progress :percentage="system.resources.cpu" :stroke-width="8" :color="cpuColor" />
            </div>
            <div class="resource-item">
              <div class="resource-label">
                <span>内存</span>
                <span>{{ system.resources.memory }}%</span>
              </div>
              <el-progress :percentage="system.resources.memory" :stroke-width="8" :color="memColor" />
            </div>
            <div class="resource-item">
              <div class="resource-label">
                <span>磁盘</span>
                <span>{{ system.resources.disk }}%</span>
              </div>
              <el-progress :percentage="system.resources.disk" :stroke-width="8" :color="diskColor" />
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useSystemStore } from '@/stores/system'
import {
  DocumentCopy, WarningFilled, CircleCheckFilled, DataBoard,
} from '@element-plus/icons-vue'

interface LatestRecord {
  barcode: string
  device_id: string
  processed_at: string
}

const system = useSystemStore()

const latestRecords = computed<LatestRecord[]>(() => {
  return []
})

const cards = computed(() => [
  {
    icon: DataBoard,
    label: '今日数据',
    value: system.todayDataCount.toLocaleString(),
    unit: '条',
    footer: '今日已采集',
    accent: '#3B82F6',
  },
  {
    icon: DocumentCopy,
    label: '累计数据',
    value: system.totalRecords.toLocaleString(),
    unit: '条',
    footer: `来自 ${system.deviceCount} 个设备`,
    accent: '#059669',
  },
  {
    icon: WarningFilled,
    label: '待审批',
    value: system.pendingApprovals.toLocaleString(),
    unit: '项',
    footer: '参数变更待处理',
    accent: '#D97706',
  },
  {
    icon: CircleCheckFilled,
    label: '服务状态',
    value: system.serviceStatus === 'healthy' ? '正常' : '异常',
    unit: '',
    footer: system.serviceStatus === 'healthy' ? '所有服务运行中' : '部分服务异常',
    accent: system.serviceStatus === 'healthy' ? '#059669' : '#DC2626',
  },
])

function formatTime(iso: string) {
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

const cpuColor = computed(() => {
  const v = system.resources.cpu
  return v > 80 ? '#DC2626' : v > 50 ? '#D97706' : '#059669'
})
const memColor = computed(() => {
  const v = system.resources.memory
  return v > 80 ? '#DC2626' : v > 50 ? '#D97706' : '#059669'
})
const diskColor = computed(() => {
  const v = system.resources.disk
  return v > 80 ? '#DC2626' : v > 50 ? '#D97706' : '#059669'
})

onMounted(() => {
  system.loadStats()
})
</script>

<style scoped>
.dashboard {
}

.dashboard-header {
  margin-bottom: 16px;
}

.page-title {
  font-family: 'Fira Code', monospace;
  font-size: 20px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0 0 2px;
}

.page-desc {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin: 0;
}

.stat-card {
  background: var(--el-fill-color);
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 14px;
  animation: cardSlide 0.4s ease-out both;
  animation-delay: calc(var(--i) * 0.08s);
}

@keyframes cardSlide {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.stat-card-header {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  margin-bottom: 8px;
}

.stat-card-value {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-bottom: 4px;
}

.stat-number {
  font-family: 'Fira Code', monospace;
  font-size: 26px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  line-height: 1;
}

.stat-unit {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.stat-card-footer {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

.stat-card:hover {
  border-color: var(--el-color-primary);
  transition: border-color 0.2s;
}

.dashboard-secondary {
  margin-top: 12px;
}

.section-card {
  margin-bottom: 12px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  font-weight: 500;
}

.record-list {
  display: flex;
  flex-direction: column;
}

.record-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px solid var(--el-border-color-light);
  animation: rowIn 0.3s ease-out both;
  animation-delay: calc(var(--i) * 0.05s);
}

@keyframes rowIn {
  from { opacity: 0; transform: translateX(-8px); }
  to { opacity: 1; transform: translateX(0); }
}

.record-row:last-child {
  border-bottom: none;
}

.record-barcode {
  font-family: 'Fira Code', monospace;
  font-size: 13px;
  color: var(--el-text-color-primary);
}

.record-device {
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.record-time {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-family: 'Fira Code', monospace;
}

.resource-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.resource-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.resource-label {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: var(--el-text-color-regular);
}
</style>

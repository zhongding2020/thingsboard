<template>
  <div class="settings">
    <el-row :gutter="20">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>服务状态</template>
          <div>
            <el-descriptions :column="2" border>
              <el-descriptions-item label="服务状态">
                <el-tag :type="statusTagType">{{ system.serviceStatus }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="CPU">{{ system.resources.cpu }}%</el-descriptions-item>
              <el-descriptions-item label="内存">{{ system.resources.memory }}%</el-descriptions-item>
              <el-descriptions-item label="磁盘">{{ system.resources.disk }}%</el-descriptions-item>
            </el-descriptions>
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>日志</template>
          <div class="log-area">
            <p v-for="(log, index) in logs" :key="index" class="log-line">{{ log }}</p>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useSystemStore } from '@/stores/system'

const system = useSystemStore()

const statusTagType = computed(() => {
  switch (system.serviceStatus) {
    case 'healthy': return 'success'
    case 'degraded': return 'warning'
    case 'down': return 'danger'
    default: return 'info'
  }
})

const logs = ref([
  '[2024-01-01 00:00:00] 服务启动',
  '[2024-01-01 00:01:00] 参数集已加载',
  '[2024-01-01 00:02:00] 数据库连接成功',
])
</script>

<style scoped>
.settings {
}
.log-area {
  height: 300px;
  overflow-y: auto;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-regular);
  padding: 10px;
  font-family: monospace;
  font-size: 12px;
}
.log-line {
  margin: 2px 0;
}
</style>

<template>
  <div class="agent-header">
    <div class="agent-header-left">
      <el-dropdown trigger="click" @command="$emit('switchModel', $event)">
        <el-button text size="small" class="model-btn">
          {{ currentModelLabel }}
          <el-icon><ArrowDown /></el-icon>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item v-for="m in models" :key="m.value" :command="m.value" :class="{ 'is-active': m.value === currentModel }">{{ m.label }}</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
    <div class="agent-header-title">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M12 3l2.5 5.5L20 9.5l-4 4 .5 5.5L12 16l-4.5 3 .5-5.5-4-4L9.5 8.5z"/></svg>
      AI
    </div>
    <div class="agent-header-right">
      <el-button text size="small" @click="$emit('toggleSessions')" :title="showSessions ? '返回' : '历史'">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
      </el-button>
      <el-button text size="small" @click="$emit('newSession')" title="新建">+</el-button>
      <el-button text size="small" @click="$emit('toggleMaximize')" :title="maximized ? '还原' : '最大化'">
        <svg v-if="!maximized" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>
        <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="8" y="8" width="12" height="12" rx="2"/><rect x="4" y="4" width="12" height="12" rx="2"/></svg>
      </el-button>
      <el-button text size="small" @click="$emit('close')" title="关闭">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'

interface Model { label: string; value: string }
interface ProcessType { process_type: string; display_name: string }

const props = defineProps<{
  currentModel: string
  models: Model[]
  processTypes: ProcessType[]
  currentProcessType: string
  showSessions: boolean
  maximized: boolean
}>()

defineEmits<{
  switchModel: [val: string]
  switchProcess: [val: string]
  toggleSessions: []
  newSession: []
  toggleMaximize: []
  close: []
}>()

const currentModelLabel = computed(() => props.models.find(m => m.value === props.currentModel)?.label || '')
</script>

<style scoped>
.agent-header { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border-bottom: 1px solid var(--el-border-color-light); flex-shrink: 0; gap: 8px; }
.agent-header-title { display: flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 600; color: #6366f1; }
.agent-header-right { display: flex; align-items: center; gap: 2px; }
.model-btn { font-size: 12px; color: var(--el-text-color-secondary); }
</style>

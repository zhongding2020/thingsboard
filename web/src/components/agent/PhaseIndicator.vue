<template>
  <div class="phase-indicator" v-if="phase">
    <div class="phase-bar">
      <template v-for="(p, i) in phases" :key="p.key">
        <div class="phase-step" :class="phaseClass(p.key)" @click="$emit('selectPhase', p.key)">
          <span class="phase-dot">{{ dotChar(p.key) }}</span>
          <span class="phase-label">{{ p.label }}</span>
        </div>
        <div v-if="i < phases.length - 1" class="phase-connector" :class="{ active: isDone(p.key) || isCurrent(p.key) }" />
      </template>
    </div>
    <div class="phase-hint">{{ currentLabel }} — {{ hintText }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ phase: string }>()
defineEmits<{ selectPhase: [key: string] }>()

const phases = [
  { key: 'define', label: 'Define', hint: '明确优化目标与基准' },
  { key: 'explore', label: 'Explore', hint: '探索数据与设计实验' },
  { key: 'analyze', label: 'Analyze', hint: '数据分析与建模' },
  { key: 'optimize', label: 'Optimize', hint: '参数推荐与优化' },
  { key: 'verify', label: 'Verify', hint: '验证与闭环控制' },
]

const phaseOrder = phases.map(p => p.key)
const currentIdx = computed(() => phaseOrder.indexOf(props.phase))

function isDone(key: string) { return phaseOrder.indexOf(key) < currentIdx.value }
function isCurrent(key: string) { return key === props.phase }

function phaseClass(key: string) {
  if (isDone(key)) return 'done'
  if (isCurrent(key)) return 'current'
  return 'pending'
}

function dotChar(key: string) {
  if (isDone(key)) return '✓'
  if (isCurrent(key)) return '●'
  return '○'
}

const currentLabel = computed(() => phases.find(p => p.key === props.phase)?.label || '')
const hintText = computed(() => phases.find(p => p.key === props.phase)?.hint || '')
</script>

<style scoped>
.phase-indicator {
  padding: 8px 14px 6px;
  border-bottom: 1px solid var(--el-border-color-light);
  background: var(--el-color-primary-light-9);
}
.phase-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
}
.phase-step {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  transition: background 0.15s;
  white-space: nowrap;
}
.phase-step:hover { background: var(--el-fill-color); }
.phase-dot { font-size: 10px; flex-shrink: 0; }
.phase-label { font-size: 11px; }
.phase-step.done .phase-dot { color: var(--el-color-success); }
.phase-step.done .phase-label { color: var(--el-color-success); }
.phase-step.current .phase-dot { color: var(--el-color-primary); animation: pulse 1.2s infinite; }
.phase-step.current .phase-label { color: var(--el-color-primary); font-weight: 600; }
.phase-step.pending .phase-dot { color: var(--el-text-color-placeholder); }
.phase-step.pending .phase-label { color: var(--el-text-color-placeholder); }
.phase-connector {
  width: 20px; height: 1px;
  background: var(--el-border-color);
  flex-shrink: 0; margin: 0 2px;
}
.phase-connector.active { background: var(--el-color-success); }
.phase-hint {
  text-align: center; font-size: 11px;
  color: var(--el-text-color-secondary); margin-top: 4px;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>

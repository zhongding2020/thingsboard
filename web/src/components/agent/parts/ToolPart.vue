<template>
  <div class="tool-part">
    <div
      class="tool-header"
      :class="stateClass"
      @click="expanded = !expanded"
    >
      <span class="tool-icon" v-html="icon"></span>
      <span class="tool-name">{{ part.toolName || part.type }}</span>
      <span class="tool-badge">{{ stateLabel }}</span>
      <span class="expand-arrow" v-html="expanded ? arrowUp : arrowDown"></span>
    </div>
    <div v-if="expanded" class="tool-body">
      <template v-if="isAskUser">
        <div class="ask-user-wrapper">
          <p class="ask-user-title">{{ userAction?.title || '请选择' }}</p>
          <ActionSelect
            v-if="userAction?.type === 'select'"
            :options="userAction.options || []"
            :model-value="userAction.defaultValue"
            @select="handleSelect"
          />
          <ActionMultiSelect
            v-else-if="userAction?.type === 'multi_select'"
            :options="userAction.options || []"
            :model-value="userAction.defaultValue"
            @select="handleMultiSelect"
          />
          <ActionConfirm
            v-else-if="userAction?.type === 'confirm'"
            :confirm-text="userAction.confirmText || '确认'"
            :cancel-text="userAction.cancelText || '取消'"
            @confirm="handleConfirm(true)"
            @cancel="handleConfirm(false)"
          />
          <ActionInput
            v-else-if="userAction?.type === 'input'"
            :placeholder="userAction.placeholder || '请输入'"
            :model-value="userAction.defaultValue"
            @submit="handleInput"
          />
          <ActionCascader
            v-else-if="userAction?.type === 'cascader'"
            :levels="userAction.cascaderLevels || []"
            @complete="handleCascader"
          />
        </div>
      </template>
      <div v-else class="tool-result markdown-body" v-html="resultHtml" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { marked } from 'marked'
import ActionSelect from '../ActionSelect.vue'
import ActionMultiSelect from '../ActionMultiSelect.vue'
import ActionConfirm from '../ActionConfirm.vue'
import ActionInput from '../ActionInput.vue'
import ActionCascader from '../ActionCascader.vue'

const props = defineProps<{ part: any }>()
const emit = defineEmits<{ output: [toolCallId: string, output: unknown] }>()

const expanded = ref(true)

const arrowDown = '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M6 9l6 6 6-6"/></svg>'
const arrowUp = '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M18 15l-6-6-6 6"/></svg>'

const isAskUser = computed(() => props.part.type === 'tool-ask_user')
const userAction = computed(() => {
  if (!isAskUser.value) return null
  return {
    type: props.part.input?.type || 'select',
    title: props.part.input?.title,
    options: props.part.input?.options,
    cascaderLevels: props.part.input?.cascaderLevels,
    confirmText: props.part.input?.confirmText,
    cancelText: props.part.input?.cancelText,
    placeholder: props.part.input?.placeholder,
    defaultValue: props.part.input?.defaultValue,
  }
})

const stateClass = computed(() => {
  if (isAskUser.value) return 'state-pending'
  if (props.part.state === 'output-available') return 'state-done'
  if (props.part.state === 'output-error') return 'state-error'
  if (props.part.state === 'input-available') return 'state-running'
  return 'state-pending'
})

const icon = computed(() => {
  if (isAskUser.value) return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg>'
  if (props.part.state === 'output-available') return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>'
  if (props.part.state === 'output-error') return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><path d="M15 9l-6 6M9 9l6 6"/></svg>'
  return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>'
})

const stateLabel = computed(() => {
  if (isAskUser.value) return '等待操作'
  if (props.part.state === 'output-available') return '完成'
  if (props.part.state === 'output-error') return '错误'
  if (props.part.state === 'input-available') return '处理中'
  return '等待'
})

const resultHtml = computed(() => {
  const out = props.part.output || props.part.result || ''
  const html = marked.parse(out, { breaks: true })
  return typeof html === 'string' ? html : ''
})

function handleSelect(value: string) {
  emit('output', props.part.toolCallId, value)
}
function handleMultiSelect(values: string[]) {
  emit('output', props.part.toolCallId, values.join(','))
}
function handleConfirm(confirmed: boolean) {
  emit('output', props.part.toolCallId, confirmed ? 'Yes, confirmed.' : 'No, denied.')
}
function handleInput(value: string) {
  emit('output', props.part.toolCallId, value)
}
function handleCascader(values: Record<string, string>) {
  emit('output', props.part.toolCallId, JSON.stringify(values))
}
</script>

<style scoped>
.tool-part {
  border: 1px solid var(--el-border-color, #e2e8f0);
  border-radius: 8px;
  margin: 6px 0;
  overflow: hidden;
  background: var(--el-fill-color-blank, #fff);
}

.tool-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: var(--el-fill-color-lighter, #f8fafc);
  cursor: pointer;
  font-size: 12px;
  user-select: none;
  color: var(--el-text-color-regular, #334155);
}

.tool-name {
  font-weight: 600;
  flex: 1;
  color: var(--el-text-color-primary, #0f172a);
}

.tool-badge {
  font-size: 10px;
  padding: 1px 7px;
  border-radius: 10px;
  font-weight: 500;
}

.state-pending .tool-badge {
  background: var(--el-color-warning-light-9, #fffbeb);
  color: var(--el-color-warning-dark-2, #b45309);
}

.state-running .tool-badge {
  background: var(--el-color-primary-light-9, #eff6ff);
  color: var(--el-color-primary-dark-2, #1d4ed8);
}

.state-done .tool-badge {
  background: var(--el-color-success-light-9, #ecfdf5);
  color: var(--el-color-success-dark-2, #047857);
}

.state-error .tool-badge {
  background: var(--el-color-danger-light-9, #fef2f2);
  color: var(--el-color-danger-dark-2, #b91c1c);
}

.expand-arrow {
  display: flex;
  align-items: center;
  color: var(--el-text-color-disabled, #94a3b8);
  flex-shrink: 0;
}

.tool-icon {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.state-pending .tool-icon { color: var(--el-color-warning, #d97706); }
.state-running .tool-icon { color: var(--el-color-primary, #2563eb); }
.state-done .tool-icon { color: var(--el-color-success, #059669); }
.state-error .tool-icon { color: var(--el-color-danger, #dc2626); }

.tool-body {
  padding: 8px 12px;
  font-size: 13px;
  border-top: 1px solid var(--el-border-color, #e2e8f0);
  color: var(--el-text-color-regular, #334155);
}

.ask-user-wrapper {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ask-user-title {
  font-size: 13px;
  font-weight: 500;
  margin: 0;
  color: var(--el-text-color-primary, #0f172a);
}

.tool-result :deep(p) {
  margin: 0.3em 0;
}

.tool-result :deep(code) {
  background: var(--el-fill-color-light, #f1f5f9);
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 0.9em;
  font-family: 'Fira Code', monospace;
}
</style>

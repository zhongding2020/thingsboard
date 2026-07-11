<template>
  <div class="tool-part">
    <div
      class="tool-header"
      :class="stateClass"
      @click="expanded = !expanded"
    >
      <span class="tool-icon">{{ icon }}</span>
      <span class="tool-name">{{ part.toolName || part.type }}</span>
      <span class="tool-badge">{{ stateLabel }}</span>
      <span class="expand-arrow">{{ expanded ? '▼' : '▶' }}</span>
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
  if (isAskUser.value) return '🔘'
  if (props.part.state === 'output-available') return '✅'
  if (props.part.state === 'output-error') return '❌'
  return '⚙️'
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
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  margin: 6px 0;
  overflow: hidden;
}
.tool-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: #f9fafb;
  cursor: pointer;
  font-size: 12px;
  user-select: none;
}
.tool-name { font-weight: 600; flex: 1; }
.tool-badge { font-size: 10px; padding: 1px 6px; border-radius: 10px; }
.state-pending .tool-badge { background: #fef3c7; color: #92400e; }
.state-running .tool-badge { background: #dbeafe; color: #1e40af; }
.state-done .tool-badge { background: #d1fae5; color: #065f46; }
.state-error .tool-badge { background: #fee2e2; color: #991b1b; }
.expand-arrow { font-size: 9px; color: #9ca3af; }
.tool-body { padding: 8px 12px; font-size: 13px; border-top: 1px solid #e5e7eb; }
.ask-user-wrapper {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ask-user-title { font-size: 13px; font-weight: 500; margin: 0; color: #374151; }
</style>

<template>
  <div class="agent-input">
    <div class="input-card" :class="{ focused }">
      <textarea
        v-model="text"
        class="input-textarea"
        placeholder="输入分析需求..."
        :disabled="disabled"
        rows="3"
        @focus="focused = true"
        @blur="focused = false"
        @keydown.enter.exact.prevent="emitSend"
        @keydown.shift.enter.prevent="text += '\n'"
      />
      <div class="toolbar">
        <div class="toolbar-left">
          <button class="tool-btn workflow-btn" title="工艺参数调优向导" @click="$emit('startWorkflow')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l2.4 7.2L22 9.5l-5.7 4.8L17.8 22 12 18l-5.8 4 1.3-7.7L2 9.5l7.6-.3z"/></svg>
            <span class="tool-label">工艺调优</span>
          </button>
          <input type="file" ref="fileInputRef" accept=".xlsx,.xls,.csv" @change="onFileChange" style="display:none" />
          <button class="tool-btn" title="上传数据文件 (.xlsx/.xls/.csv)" @click="(fileInputRef as HTMLInputElement).click()">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17,8 12,3 7,8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            <span class="tool-label">上传文件</span>
          </button>
        </div>
        <div class="toolbar-right">
          <span v-if="text.trim()" class="char-hint">{{ text.length }}</span>
          <button class="send-btn" :disabled="!text.trim() || disabled" @click="emitSend">
            <svg v-if="disabled" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="2" y="2" width="20" height="20" rx="4"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
            <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22,2 15,22 11,13 2,9"/></svg>
            <span class="send-label">发送</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

defineProps<{ disabled: boolean }>()
const emit = defineEmits<{ send: [text: string]; upload: [file: File]; startWorkflow: [] }>()

const text = ref('')
const fileInputRef = ref<HTMLInputElement>()
const focused = ref(false)

function emitSend() {
  const val = text.value.trim()
  if (!val) return
  emit('send', val)
  text.value = ''
}

function onFileChange(e: Event) {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) emit('upload', file)
  target.value = ''
}
</script>

<style scoped>
.agent-input {
  padding: 12px 14px 14px;
  background: transparent;
}
.input-card {
  border: 1.5px solid var(--el-border-color);
  border-radius: 14px;
  background: var(--el-fill-color);
  overflow: hidden;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.input-card.focused {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}
.input-textarea {
  width: 100%;
  border: none;
  outline: none;
  background: transparent;
  font-size: 14px;
  line-height: 1.6;
  resize: none;
  font-family: inherit;
  color: var(--el-text-color-primary);
  padding: 12px 14px 4px;
  box-sizing: border-box;
}
.input-textarea::placeholder {
  color: var(--el-text-color-placeholder);
}
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 10px 8px;
}
.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 4px;
}
.tool-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--el-text-color-regular);
  cursor: pointer;
  font-size: 12px;
  font-family: inherit;
  transition: background 0.15s;
}
.tool-btn:hover {
  background: var(--el-fill-color-light);
}
.tool-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.send-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 14px;
  border: none;
  border-radius: 6px;
  background: var(--el-color-primary);
  color: #fff;
  cursor: pointer;
  font-size: 12px;
  font-family: inherit;
  transition: opacity 0.15s, background 0.15s;
}
.send-btn:hover:not(:disabled) {
  opacity: 0.9;
}
.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.send-label {
  font-size: 12px;
}
.char-hint {
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  color: var(--el-text-color-placeholder);
}
.workflow-btn { color: var(--el-color-warning); }
.workflow-btn:hover { background: var(--el-color-warning-light-9); }
</style>

<template>
  <div class="chat-input-area">
    <div class="input-wrapper">
      <textarea
        ref="textareaRef"
        v-model="text"
        class="input-textarea"
        placeholder="输入分析需求，例如：分析最近100条数据..."
        :disabled="disabled"
        rows="1"
        @keydown.enter.exact.prevent="emitSend"
        @keydown.shift.enter.prevent="text += '\n'"
        @input="autoResize"
      />
    </div>
    <div class="input-footer">
      <div class="footer-hint">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
        <span>Enter 发送 · Shift+Enter 换行</span>
      </div>
      <div class="footer-actions">
        <button v-if="disabled && canStop" class="btn btn-stop" @click="$emit('stop')">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="6" y="6" width="12" height="12" rx="1"/></svg>
          停止
        </button>
        <button
          v-else
          class="btn btn-send"
          :disabled="disabled || !text.trim()"
          @click="emitSend"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
          发送
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'

const props = defineProps<{ disabled?: boolean; canStop?: boolean }>()
const emit = defineEmits<{ send: [text: string]; stop: [] }>()

const text = ref('')
const textareaRef = ref<HTMLTextAreaElement>()

function autoResize() {
  if (textareaRef.value) {
    textareaRef.value.style.height = 'auto'
    textareaRef.value.style.height = Math.min(textareaRef.value.scrollHeight, 150) + 'px'
  }
}

function emitSend() {
  if (props.disabled || !text.value.trim()) return
  emit('send', text.value.trim())
  text.value = ''
  nextTick(autoResize)
}
</script>

<style scoped>
.chat-input-area {
  border-top: 1px solid var(--el-border-color, #e2e8f0);
  padding: 8px 16px 12px;
  background: var(--el-fill-color, #fff);
}

.input-wrapper {
  border: 1px solid var(--el-border-color-dark, #cbd5e1);
  border-radius: 12px;
  padding: 8px 12px;
  background: var(--el-bg-color, #f8fafc);
  transition: border-color 0.15s, box-shadow 0.15s;
}

.input-wrapper:focus-within {
  border-color: var(--el-color-primary, #2563eb);
  box-shadow: 0 0 0 3px var(--el-color-primary-light-8, rgba(37, 99, 235, 0.1));
  background: var(--el-fill-color-blank, #fff);
}

.input-textarea {
  width: 100%;
  border: none;
  outline: none;
  background: transparent;
  font-size: 14px;
  line-height: 1.5;
  resize: none;
  color: var(--el-text-color-primary, #0f172a);
  box-sizing: border-box;
  min-height: 22px;
  max-height: 150px;
  font-family: inherit;
}

.input-textarea::placeholder {
  color: var(--el-text-color-placeholder, #94a3b8);
}

.input-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 6px;
}

.footer-hint {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--el-text-color-disabled, #94a3b8);
}

.footer-actions {
  display: flex;
  gap: 6px;
}

.btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 14px;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  font-family: inherit;
  line-height: 1;
}

.btn-send {
  background: var(--el-color-primary, #2563eb);
  color: #fff;
}

.btn-send:hover:not(:disabled) {
  background: var(--el-color-primary-dark-2, #1d4ed8);
}

.btn-send:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.btn-stop {
  background: var(--el-color-danger-light-9, #fef2f2);
  color: var(--el-color-danger, #dc2626);
  border: 1px solid var(--el-color-danger-light-7, #fecaca);
}

.btn-stop:hover {
  background: var(--el-color-danger, #dc2626);
  color: #fff;
}
</style>

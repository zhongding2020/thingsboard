<template>
  <div class="chat-input-area">
    <div class="input-wrapper">
      <textarea
        ref="textareaRef"
        v-model="text"
        class="input-textarea"
        placeholder="输入分析需求..."
        :disabled="disabled"
        rows="1"
        @keydown.enter.exact.prevent="emitSend"
        @keydown.shift.enter.prevent="text += '\n'"
        @input="autoResize"
      />
    </div>
    <div class="input-footer">
      <div class="footer-spacer" />
      <div class="footer-actions">
        <button v-if="disabled && canStop" class="btn btn-stop" @click="$emit('stop')">
          ⏹ 停止
        </button>
        <button
          v-else
          class="btn btn-send"
          :disabled="disabled || !text.trim()"
          @click="emitSend"
        >
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

defineExpose({ text })
</script>

<style scoped>
.chat-input-area {
  border-top: 1px solid #e5e7eb;
  padding: 10px 14px 12px;
}
.input-wrapper {
  border: 1px solid #d1d5db;
  border-radius: 12px;
  padding: 6px 10px;
  background: #fff;
  transition: border-color 0.15s;
}
.input-wrapper:focus-within {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59,130,246,0.15);
}
.input-textarea {
  width: 100%;
  border: none;
  outline: none;
  background: transparent;
  font-size: 14px;
  line-height: 1.5;
  resize: none;
  color: #1f2937;
  box-sizing: border-box;
  min-height: 24px;
  max-height: 150px;
}
.input-textarea::placeholder { color: #9ca3af; }
.input-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 6px;
}
.btn {
  padding: 6px 16px;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-send {
  background: #3b82f6;
  color: #fff;
}
.btn-send:hover:not(:disabled) { background: #2563eb; }
.btn-send:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-stop {
  background: #ef4444;
  color: #fff;
}
.btn-stop:hover { background: #dc2626; }
</style>

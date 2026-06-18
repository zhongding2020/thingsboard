<template>
  <div class="agent-input">
    <div class="input-wrapper">
      <div class="upload-btn-wrapper">
        <input type="file" ref="fileInputRef" accept=".xlsx,.xls,.csv" @change="onFileChange" style="display:none" />
        <el-button text size="small" @click="(fileInputRef as HTMLInputElement).click()" title="上传数据文件">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17,8 12,3 7,8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
        </el-button>
      </div>
      <textarea v-model="text" class="input-textarea" placeholder="输入分析需求... &#8629; 发送" :disabled="disabled" rows="3" @keydown.enter.exact.prevent="emitSend" />
      <el-button class="input-send" type="primary" size="small" @click="emitSend" :disabled="!text.trim() || disabled" :loading="disabled">
        <svg v-if="!disabled" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22,2 15,22 11,13 2,9"/></svg>
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

defineProps<{ disabled: boolean }>()
const emit = defineEmits<{ send: [text: string]; upload: [file: File] }>()

const text = ref('')
const fileInputRef = ref<HTMLInputElement>()

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
.agent-input { padding: 10px 14px 14px; border-top: 1px solid var(--el-border-color-light); }
.input-wrapper { display: flex; align-items: flex-end; gap: 8px; background: var(--el-fill-color); border-radius: 14px; padding: 8px 10px; border: 1px solid var(--el-border-color-light); transition: border-color 0.2s; }
.input-wrapper:focus-within { border-color: var(--el-color-primary); }
.input-textarea { flex: 1; border: none; outline: none; background: transparent; font-size: 13px; line-height: 1.5; resize: none; font-family: inherit; color: var(--el-text-color-primary); padding: 2px 4px; }
.input-textarea::placeholder { color: var(--el-text-color-placeholder); }
.input-send { flex-shrink: 0; border-radius: 10px; }
.upload-btn-wrapper { display: flex; align-items: center; padding: 2px; }
</style>

<template>
  <div class="px-4 pb-4 pt-2">
    <div
      class="border border-gray-200 dark:border-gray-700 rounded-2xl bg-gray-50 dark:bg-gray-900 overflow-hidden transition-colors focus-within:border-indigo-400 focus-within:ring-2 focus-within:ring-indigo-400/20"
    >
      <textarea
        v-model="text"
        class="w-full border-none outline-none bg-transparent text-sm leading-relaxed resize-none font-sans text-gray-800 dark:text-gray-200 placeholder-gray-400 px-4 pt-3 pb-1 box-border"
        placeholder="输入分析需求..."
        :disabled="disabled"
        rows="3"
        @keydown.enter.exact.prevent="emitSend"
        @keydown.shift.enter.prevent="text += '\n'"
      />
      <div class="flex items-center justify-between px-3 pb-3">
        <div class="flex items-center gap-1">
          <button
            class="flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg bg-transparent text-amber-500 hover:bg-amber-50 dark:hover:bg-amber-950 border-none cursor-pointer transition-colors"
            @click="$emit('startWorkflow')"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l2.4 7.2L22 9.5l-5.7 4.8L17.8 22 12 18l-5.8 4 1.3-7.7L2 9.5l7.6-.3z"/></svg>
            工艺调优
          </button>
          <input
            ref="fileRef"
            type="file"
            class="hidden"
            accept=".xlsx,.xls,.csv"
            @change="onFileChange"
          />
          <button
            class="flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg bg-transparent text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 border-none cursor-pointer transition-colors"
            @click="(fileRef as HTMLInputElement)?.click()"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17,8 12,3 7,8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            上传
          </button>
        </div>
        <div class="flex items-center gap-2">
          <span v-if="text.trim()" class="text-[11px] tabular-nums text-gray-300">{{ text.length }}</span>
          <button
            v-if="disabled"
            class="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-red-500 hover:bg-red-600 text-white border-none cursor-pointer transition-colors"
            @click="$emit('stop')"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="3"/></svg>
            停止
          </button>
          <button
            v-else
            class="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-indigo-500 hover:bg-indigo-600 text-white border-none cursor-pointer transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            :disabled="!text.trim()"
            @click="emitSend"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22,2 15,22 11,13 2,9"/></svg>
            发送
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

defineProps<{ disabled: boolean }>()
const emit = defineEmits<{
  send: [text: string]
  upload: [file: File]
  startWorkflow: []
  stop: []
}>()

const text = ref('')
const fileRef = ref<HTMLInputElement>()

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

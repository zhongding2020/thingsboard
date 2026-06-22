<template>
  <div class="flex items-center gap-2">
    <button
      class="px-4 py-1.5 text-[11px] rounded-md bg-blue-500 hover:bg-blue-600 text-white border-none cursor-pointer transition-colors"
      @click="emit('resolve', { confirmed: true })"
    >{{ action.confirmText || '确认' }}</button>
    <button
      class="px-4 py-1.5 text-[11px] rounded-md bg-transparent hover:bg-gray-100 dark:hover:bg-gray-800 text-slate-500 border border-slate-200 dark:border-slate-700 cursor-pointer transition-colors"
      @click="emit('resolve', { confirmed: false })"
    >{{ action.cancelText || '取消' }}</button>
  </div>
</template>

<script setup lang="ts">
import type { InteractiveAction } from '@/composables/useAgentStream'

defineProps<{ action: InteractiveAction }>()
const emit = defineEmits<{ resolve: [value: unknown] }>()
</script>

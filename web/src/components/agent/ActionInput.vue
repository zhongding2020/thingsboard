<template>
  <div class="flex items-center gap-2">
    <el-input
      v-model="text"
      :placeholder="action.placeholder || '请输入'"
      size="small"
      class="flex-1"
      @keydown.enter="submit"
    />
    <button
      :disabled="!text.trim()"
      class="px-3 py-1 text-[11px] rounded-md bg-blue-500 hover:bg-blue-600 disabled:opacity-40 text-white border-none cursor-pointer transition-colors"
      @click="submit"
    >确认</button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { InteractiveAction } from '@/composables/useAgentStream'

const props = defineProps<{ action: InteractiveAction }>()
const emit = defineEmits<{ resolve: [value: unknown] }>()

const text = ref((props.action.defaultValue as string) || '')

function submit() {
  if (!text.value.trim()) return
  emit('resolve', { value: text.value.trim() })
}
</script>

<template>
  <div class="flex items-center gap-2">
    <el-input
      v-model="text"
      :placeholder="placeholder"
      size="small"
      class="flex-1"
      @keydown.enter="submit"
    />
    <button class="submit-btn" :disabled="!text.trim()" @click="submit">确认</button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

defineProps<{ placeholder?: string; modelValue?: string }>()
const emit = defineEmits<{ submit: [value: string] }>()

const text = ref('')

function submit() {
  if (!text.value.trim()) return
  emit('submit', text.value.trim())
}
</script>

<style scoped>
.submit-btn { padding: 6px 16px; font-size: 12px; border-radius: 6px; background: #3b82f6; color: #fff; border: none; cursor: pointer; }
.submit-btn:hover:not(:disabled) { background: #2563eb; }
.submit-btn:disabled { opacity: 0.4; cursor: not-allowed; }
</style>

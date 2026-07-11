<template>
  <div class="flex items-center gap-2">
    <button class="confirm-btn" @click="$emit('confirm')">{{ confirmText || '确认' }}</button>
    <button class="cancel-btn" @click="$emit('cancel')">{{ cancelText || '取消' }}</button>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  confirmText?: string
  cancelText?: string
}>()
defineEmits<{ confirm: []; cancel: [] }>()
</script>

<style scoped>
.confirm-btn { padding: 6px 16px; font-size: 12px; border-radius: 6px; background: #3b82f6; color: #fff; border: none; cursor: pointer; }
.confirm-btn:hover { background: #2563eb; }
.cancel-btn { padding: 6px 16px; font-size: 12px; border-radius: 6px; background: transparent; color: #6b7280; border: 1px solid #d1d5db; cursor: pointer; }
.cancel-btn:hover { background: #f3f4f6; }
</style>

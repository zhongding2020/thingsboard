<template>
  <details class="my-1 border border-amber-200 dark:border-amber-800 rounded-lg px-3 py-2 text-xs bg-amber-50 dark:bg-amber-900/30" :open="isStreaming">
    <summary class="cursor-pointer text-amber-600 dark:text-amber-400 font-medium select-none">
      🤔 {{ isStreaming ? '思考中...' : '思考过程' }}
    </summary>
    <div class="mt-2 text-amber-800 dark:text-amber-200 leading-relaxed whitespace-pre-wrap">{{ text }}</div>
  </details>
</template>

<script setup lang="ts">
defineProps<{ text: string; isStreaming?: boolean }>()
</script>

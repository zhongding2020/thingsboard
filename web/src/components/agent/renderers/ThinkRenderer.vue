<template>
  <details class="my-1 border border-amber-200 dark:border-amber-800 rounded-lg px-3 py-2 text-xs bg-amber-50 dark:bg-amber-900/30">
    <summary class="cursor-pointer text-amber-600 dark:text-amber-400 font-medium select-none">
      &#x1F914; 推理/思考
    </summary>
    <div class="mt-2 text-amber-800 dark:text-amber-200 leading-relaxed whitespace-pre-wrap">{{ data }}</div>
  </details>
</template>

<script setup lang="ts">
defineProps<{ data: string }>()
</script>

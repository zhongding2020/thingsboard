<template>
  <div class="text-part markdown-body">
    <div v-html="rendered" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'

const props = defineProps<{ text: string }>()

const rendered = computed(() => {
  const html = marked.parse(props.text || '', { breaks: true })
  return typeof html === 'string' ? html : ''
})
</script>

<style scoped>
.text-part { line-height: 1.6; }
.text-part :deep(p) { margin: 0.3em 0; }
.text-part :deep(code) { background: #f3f4f6; padding: 1px 4px; border-radius: 3px; font-size: 0.9em; }
.text-part :deep(pre code) { background: none; padding: 0; }
.text-part :deep(table) { border-collapse: collapse; width: 100%; margin: 0.5em 0; }
.text-part :deep(th), .text-part :deep(td) { border: 1px solid #e5e7eb; padding: 4px 8px; text-align: left; }
.text-part :deep(th) { background: #f9fafb; font-weight: 600; }
.text-part :deep(hr) { border: none; border-top: 1px solid #e5e7eb; margin: 1em 0; }
.text-part :deep(ul), .text-part :deep(ol) { padding-left: 1.5em; }
.text-part :deep(blockquote) { border-left: 3px solid #d1d5db; padding-left: 0.8em; color: #6b7280; }
</style>

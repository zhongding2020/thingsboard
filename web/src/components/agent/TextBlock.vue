<template>
  <div class="prose prose-sm max-w-none dark:prose-invert animate-streamdown" v-html="rendered" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'

const props = defineProps<{ text: string; isStreaming?: boolean }>()
const rendered = computed(() => marked.parse(props.text || '', { breaks: true, gfm: true }) as string)
</script>

<style scoped>
@keyframes streamdown {
  from { opacity: 0; transform: translateY(-6px); }
  to { opacity: 1; transform: translateY(0); }
}
.animate-streamdown { animation: streamdown 0.25s ease-out; }

/* Scale down prose typography to match chat's compact 11-12px system */
:deep(p)    { font-size: 12px; line-height: 1.65; margin: 0 0 6px; }
:deep(p:last-child) { margin-bottom: 0; }
:deep(h1)   { font-size: 15px; margin: 10px 0 4px; }
:deep(h2)   { font-size: 14px; margin: 8px 0 4px; }
:deep(h3)   { font-size: 13px; margin: 6px 0 3px; }
:deep(h4)   { font-size: 12px; margin: 6px 0 3px; }
:deep(ul), :deep(ol) { font-size: 12px; padding-left: 18px; margin: 4px 0; }
:deep(li)   { font-size: 12px; line-height: 1.6; margin-bottom: 2px; }
:deep(li:last-child) { margin-bottom: 0; }
:deep(code) { font-size: 11px; background: #e2e8f0; padding: 1px 5px; border-radius: 3px; }
:deep(pre)  { font-size: 11px; margin: 6px 0; padding: 8px 10px; border-radius: 6px; }
:deep(pre code) { font-size: 11px; background: transparent; padding: 0; }
:deep(blockquote) { font-size: 12px; margin: 6px 0; padding: 4px 10px; }
:deep(table) { font-size: 11px; }
:deep(th), :deep(td) { font-size: 11px; padding: 4px 8px; }
:deep(strong) { font-size: inherit; }
:deep(em) { font-size: inherit; }
:deep(a) { font-size: inherit; }
:deep(hr) { margin: 8px 0; }
</style>

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
</style>

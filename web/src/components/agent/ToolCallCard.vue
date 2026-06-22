<template>
  <!-- Pending call -->
  <div v-if="tc.status === 'pending'" class="my-1 border border-blue-200 dark:border-blue-800 rounded-lg px-3 py-2 text-xs bg-blue-50 dark:bg-blue-900/30 max-w-[95%]">
    <div class="flex items-center gap-2 mb-1">
      <span class="w-4 h-4 text-blue-500 animate-spin">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
      </span>
      <span class="font-medium text-blue-600 dark:text-blue-400">调用: {{ tc.name }}</span>
    </div>
    <pre v-if="tc.args && Object.keys(tc.args).length" class="m-0 text-[11px] whitespace-pre-wrap break-all text-blue-400 font-mono">{{ JSON.stringify(tc.args, null, 2) }}</pre>
  </div>

  <!-- Done result — dispatch to renderer -->
  <div v-else-if="tc.status === 'done'" class="my-1 border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-2 text-xs bg-white dark:bg-gray-900 max-w-[95%]">
    <div class="flex items-center gap-2 mb-2">
      <span class="text-green-500">✓</span>
      <span class="font-medium text-gray-500 dark:text-gray-400">
        {{ tc.name }}<span v-if="tc.durationMs"> ({{ tc.durationMs }}ms)</span>
      </span>
    </div>

    <!-- Per-tool renderer dispatch -->
    <FilesRenderer v-if="isFilesTool(tc.name)" :data="tc.result || ''" />
    <SearchRenderer v-else-if="isSearchTool(tc.name)" :data="tc.result || ''" />
    <ThinkRenderer v-else-if="isThinkTool(tc.name)" :data="tc.result || ''" />
    <TodosRenderer v-else-if="isTodoTool(tc.name)" :data="tc.result || ''" />
    <div v-else class="tool-markdown" v-html="renderMarkdown(tc.result || '')" />
  </div>

  <!-- Error -->
  <div v-if="tc.status === 'error'" class="my-1 border border-red-200 dark:border-red-800 rounded-lg px-3 py-2 text-xs bg-red-50 dark:bg-red-900/30">
    <span class="text-red-500">✗ {{ tc.name }} 失败</span>
  </div>
</template>

<script setup lang="ts">
import { marked } from 'marked'
import FilesRenderer from './renderers/FilesRenderer.vue'
import SearchRenderer from './renderers/SearchRenderer.vue'
import ThinkRenderer from './renderers/ThinkRenderer.vue'
import TodosRenderer from './renderers/TodosRenderer.vue'
import type { ToolCall } from '@/composables/useAgentStream'

defineProps<{ tc: ToolCall }>()

function renderMarkdown(text: string): string {
  return marked.parse(text, { breaks: true, gfm: true }) as string
}

function isFilesTool(name: string): boolean {
  return /file|list_files|read|write|edit/i.test(name)
}
function isSearchTool(name: string): boolean {
  return /search|query|find/i.test(name)
}
function isThinkTool(name: string): boolean {
  return /think|reason/i.test(name)
}
function isTodoTool(name: string): boolean {
  return /todo|task/i.test(name)
}
</script>

<style scoped>
.tool-markdown :deep(p) { margin: 0 0 6px; }
.tool-markdown :deep(p:last-child) { margin-bottom: 0; }
.tool-markdown :deep(table) { border-collapse: collapse; width: 100%; font-size: 11px; margin: 4px 0; }
.tool-markdown :deep(th), .tool-markdown :deep(td) { border: 1px solid #e2e8f0; padding: 3px 6px; text-align: left; }
.tool-markdown :deep(th) { background: #f1f5f9; font-weight: 500; }
</style>

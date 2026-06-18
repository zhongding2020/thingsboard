<template>
  <details v-if="type === 'reasoning' || type === 'thinking'" class="msg-reasoning" :open="isStreaming">
    <summary>{{ isStreaming ? '思考中...' : '思考过程' }}</summary>
    <div class="reasoning-content" v-html="mdText"></div>
  </details>
  <div v-else-if="type === 'tool_call'" class="msg-tool">
    <div class="tool-label">调用工具: {{ toolName }}</div>
    <pre class="tool-args" v-if="args">{{ args }}</pre>
  </div>
  <div v-else-if="type === 'tool_result'" class="msg-tool">
    <div class="tool-label">工具返回</div>
    <pre class="tool-args">{{ text }}</pre>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'

const props = defineProps<{
  type: string
  text?: string
  toolName?: string
  args?: string
  isStreaming?: boolean
}>()

const mdText = computed(() => marked.parse(props.text || '', { breaks: true, gfm: true }) as string)
</script>

<style scoped>
.msg-reasoning { margin: 2px 0; border: 1px solid var(--el-border-color-light); border-radius: 8px; padding: 6px 10px; font-size: 12px; background: var(--el-color-info-light-9); max-width: 95%; align-self: flex-start; }
.msg-reasoning summary { cursor: pointer; color: var(--el-text-color-secondary); }
.msg-reasoning[open] summary { margin-bottom: 6px; }
.reasoning-content { color: var(--el-text-color-secondary); line-height: 1.5; }
.msg-tool { margin: 2px 0; border: 1px solid var(--el-border-color-light); border-radius: 8px; padding: 6px 10px; font-size: 12px; background: var(--el-fill-color); max-width: 95%; align-self: flex-start; }
.tool-label { color: var(--el-color-primary); margin-bottom: 4px; font-weight: 500; }
.tool-args { margin: 0; font-size: 11px; white-space: pre-wrap; word-break: break-all; color: var(--el-text-color-secondary); }
</style>

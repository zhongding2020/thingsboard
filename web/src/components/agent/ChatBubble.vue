<template>
  <div class="agent-msg">
    <div v-if="msg.role === 'user'" class="msg-bubble user-msg">{{ msg.text }}</div>
    <template v-else>
      <div v-for="(part, j) in msg.parts" :key="j" class="msg-part">
        <ChatToolCall
          v-if="part.type === 'reasoning' || part.type === 'thinking'"
          :type="part.type" :text="part.text" :isStreaming="isStreaming"
        />
        <ChatToolCall
          v-else-if="part.type === 'tool_call'"
          type="tool_call" :toolName="part.tool || part.name" :args="part.args"
        />
        <ChatToolCall
          v-else-if="part.type === 'tool_result'"
          type="tool_result" :text="part.text"
        />
        <div
          v-else-if="part.type === 'text' || !part.type || part.type === 'step-start' || part.type === 'step-finish'"
          class="msg-bubble assistant-msg"
        >
          <ChatContent :text="part.text || ''" :uid="'bubble-' + msgIndex + '-' + j" />
        </div>
      </div>
      <div v-if="msg.role === 'assistant' && !isStreaming" class="msg-actions">
        <el-button text size="small" @click="$emit('copy', msg)">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
          复制
        </el-button>
        <el-button text size="small" @click="$emit('regenerate', msgIndex)">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 4v6h6"/><path d="M23 20v-6h-6"/><path d="M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15"/></svg>
          重新生成
        </el-button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import ChatContent from './ChatContent.vue'
import ChatToolCall from './ChatToolCall.vue'

interface ChatMessage { role: 'user' | 'assistant'; text: string; parts?: any[] }

defineProps<{
  msg: ChatMessage
  msgIndex: number
  isStreaming: boolean
}>()

defineEmits<{
  copy: [msg: ChatMessage]
  regenerate: [idx: number]
}>()
</script>

<style scoped>
.agent-msg { display: contents; }
.agent-msg:hover .msg-actions { opacity: 1; }
.msg-bubble { padding: 10px 14px; border-radius: 10px; font-size: 13px; line-height: 1.6; max-width: 95%; word-break: break-word; }
.user-msg { background: var(--el-color-primary-light-8); align-self: flex-end; }
.assistant-msg { align-self: flex-start; background: var(--el-fill-color); }
.msg-actions { display: flex; gap: 6px; margin-top: 4px; opacity: 0; transition: opacity 0.2s; align-self: flex-start; }
</style>

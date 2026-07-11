<template>
  <div class="message-card" :class="msg.role">
    <div class="msg-avatar">{{ msg.role === 'user' ? '👤' : '🤖' }}</div>
    <div class="msg-content">
      <div v-if="msg.role === 'user' && msg.content" class="user-text">{{ msg.content }}</div>
      <div v-else class="assistant-parts">
        <template v-for="(part, i) in msg.parts" :key="i">
          <TextPart v-if="part.type === 'text'" :text="part.text" />
          <ToolPart
            v-else-if="part.type.startsWith('tool-')"
            :part="part"
            @output="emitToolResult"
          />
          <div
            v-else-if="part.type.startsWith('data-') && part.type !== 'data-todos'"
            class="data-part"
          >{{ part.data }}</div>
        </template>
        <div v-if="loading" class="thinking-indicator">
          <span class="dot" /><span class="dot" /><span class="dot" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import TextPart from './parts/TextPart.vue'
import ToolPart from './parts/ToolPart.vue'

defineProps<{
  msg: any
  loading?: boolean
}>()
const emit = defineEmits<{ resolveAction: [toolCallId: string, value: unknown] }>()

function emitToolResult(toolCallId: string, value: unknown) {
  emit('resolveAction', toolCallId, value)
}
</script>

<style scoped>
.message-card {
  display: flex;
  gap: 10px;
  padding: 6px 0;
}
.msg-avatar { font-size: 18px; flex-shrink: 0; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; }
.msg-content { flex: 1; min-width: 0; }
.user-text {
  background: #eff6ff;
  border: 1px solid #dbeafe;
  border-radius: 12px 12px 4px 12px;
  padding: 8px 12px;
  font-size: 14px;
  line-height: 1.5;
  color: #1f2937;
  display: inline-block;
  max-width: 85%;
}
.assistant-parts { font-size: 14px; }
.thinking-indicator {
  display: flex;
  gap: 4px;
  padding: 8px 0;
}
.dot {
  width: 6px; height: 6px;
  background: #93c5fd;
  border-radius: 50%;
  animation: bounce 1.4s infinite;
}
.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce { 0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); } 40% { opacity: 1; transform: scale(1); } }
.data-part { color: #6b7280; font-size: 12px; padding: 4px 0; }
</style>

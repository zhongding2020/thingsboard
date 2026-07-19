<template>
  <div class="message-card" :class="msg.role">
    <div class="msg-avatar">
      <!-- User avatar -->
      <svg v-if="msg.role === 'user'" width="28" height="28" viewBox="0 0 48 48" fill="none">
        <rect width="48" height="48" rx="12" fill="currentColor" opacity="0.15" />
        <circle cx="24" cy="19" r="7" stroke="currentColor" stroke-width="2" fill="none" />
        <path d="M12 38c0-6.627 5.373-12 12-12s12 5.373 12 12" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" />
      </svg>
      <!-- Assistant avatar -->
      <svg v-else width="28" height="28" viewBox="0 0 48 48" fill="none">
        <rect width="48" height="48" rx="12" fill="currentColor" opacity="0.12" />
        <circle cx="24" cy="18" r="8" stroke="currentColor" stroke-width="2" fill="none" opacity="0.7" />
        <path d="M14 36c0-8 4-12 10-12s10 4 10 12" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" opacity="0.7" />
        <path d="M28 14a4 4 0 0 0-8 0" stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity="0.7" />
      </svg>
    </div>
    <div class="msg-content">
      <div class="msg-role-label">{{ msg.role === 'user' ? '操作员' : 'AI 助手' }}</div>
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
  padding: 8px 0;
  animation: msg-fade-in 0.2s ease;
}

@keyframes msg-fade-in {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

.msg-avatar {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
}

.msg-avatar svg {
  width: 28px;
  height: 28px;
}

.message-card.user .msg-avatar svg {
  color: var(--el-color-primary, #2563eb);
}

.message-card.assistant .msg-avatar svg {
  color: var(--el-color-success, #059669);
}

.msg-content {
  flex: 1;
  min-width: 0;
}

.msg-role-label {
  font-size: 11px;
  font-weight: 500;
  color: var(--el-text-color-secondary, #64748b);
  margin-bottom: 4px;
}

.user-text {
  background: var(--el-color-primary-light-9, #eff6ff);
  border: 1px solid var(--el-color-primary-light-7, #bfdbfe);
  border-radius: 12px 12px 4px 12px;
  padding: 8px 12px;
  font-size: 14px;
  line-height: 1.5;
  color: var(--el-text-color-primary, #0f172a);
  display: inline-block;
  max-width: 85%;
}

.assistant-parts {
  font-size: 14px;
  line-height: 1.6;
  color: var(--el-text-color-primary, #0f172a);
}

.thinking-indicator {
  display: flex;
  gap: 4px;
  padding: 8px 0;
}

.dot {
  width: 6px;
  height: 6px;
  background: var(--el-color-primary-light-5, #93c5fd);
  border-radius: 50%;
  animation: bounce 1.4s infinite;
}
.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes bounce {
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1); }
}

.data-part {
  color: var(--el-text-color-secondary, #64748b);
  font-size: 12px;
  padding: 4px 0;
}
</style>

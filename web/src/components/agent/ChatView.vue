<template>
  <div class="chat-view">
    <!-- Messages area -->
    <div ref="msgRef" class="messages-area">
      <!-- Welcome screen -->
      <div v-if="!messages.length" class="welcome">
        <div class="welcome-icon">
          <svg width="36" height="36" viewBox="0 0 48 48" fill="none">
            <rect x="2" y="2" width="44" height="44" rx="10" stroke="currentColor" stroke-width="2" />
            <path d="M14 30V18M20 30V22M26 30V14M32 30V26M38 30V20" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" />
            <path d="M10 34h28" stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity="0.5" />
          </svg>
        </div>
        <h1 class="welcome-title">工艺参数在线分析与调优</h1>
        <p class="welcome-subtitle">AI 驱动的制造过程优化助手，输入需求即可开始分析</p>

        <div class="use-cases">
          <button
            v-for="(uc, i) in useCases"
            :key="i"
            class="use-case-btn"
            @click="send(uc.prompt)"
          >
            <span class="uc-number">{{ String(i + 1).padStart(2, '0') }}</span>
            <span class="uc-content">
              <span class="uc-title">{{ uc.title }}</span>
              <span class="uc-desc">{{ uc.desc }}</span>
            </span>
            <svg class="uc-arrow" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M13 5l7 7-7 7"/></svg>
          </button>
        </div>
      </div>

      <!-- Messages -->
      <div v-if="messages.length" class="msg-list">
        <div
          v-for="(msg, i) in messages"
          :key="msg.id || i"
          class="msg-item"
        >
          <MessageCard
            :msg="msg"
            :loading="(status === 'submitted' || status === 'streaming') && i === messages.length - 1 && msg.role === 'assistant'"
            @resolve-action="resolveAction"
          />
        </div>
      </div>
    </div>

    <!-- Token usage bar -->
    <div v-if="estimatedTokens > 0" class="token-bar">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
      <span>上下文 tokens</span>
      <span class="token-value">{{ estimatedTokens.toLocaleString() }}</span>
    </div>

    <!-- Error bar -->
    <div v-if="error" class="error-bar">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg>
      {{ error }}
    </div>

    <!-- Input -->
    <ChatInput :disabled="status === 'submitted' || status === 'streaming'" @send="send" />
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import MessageCard from './MessageCard.vue'
import ChatInput from './ChatInput.vue'
import { useAgentChat } from '@/composables/useAgentChat'

const props = defineProps<{
  processType?: string
}>()

const {
  messages,
  sendMessage,
  status,
  error,
  estimatedTokens,
} = useAgentChat(props.processType || 'injection_molding')

const msgRef = ref<HTMLDivElement>()

const useCases = [
  { title: '分析温度参数与质量指标', desc: '自动分析设备数据相关性，识别关键影响因素', prompt: '帮我分析当前设备最近100条数据的相关性，重点关注温度参数与质量指标的关联' },
  { title: '识别关键工艺参数', desc: '特征重要性分析，锁定影响成品率的核心参数', prompt: '对设备数据做特征重要性分析，识别影响成品率的关键工艺参数' },
  { title: '过程能力分析', desc: '完整 Cpk 分析，包括控制图和过程能力指数', prompt: '对注塑成型工艺做完整过程能力分析，包括控制图和Cp/Cpk' },
  { title: '推荐最优参数组合', desc: '基于历史数据，推荐最优的工艺参数组合', prompt: '根据最近一周的生产数据，推荐最优的工艺参数组合' },
]

async function send(text: string) {
  await sendMessage({ text })
  scrollToBottom()
}

function scrollToBottom() {
  nextTick(() => {
    if (msgRef.value) msgRef.value.scrollTop = msgRef.value.scrollHeight
  })
}

async function resolveAction(_toolCallId: string, value: unknown) {
  await sendMessage({ text: `[selected: ${value}]` })
  scrollToBottom()
}
</script>

<style scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--el-bg-color, #f8fafc);
}

.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
}

.msg-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

/* Welcome screen */
.welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 16px 32px;
  max-width: 520px;
  margin: 0 auto;
}

.welcome-icon {
  color: var(--el-color-primary, #2563eb);
  opacity: 0.5;
  margin-bottom: 12px;
}

.welcome-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--el-text-color-primary, #0f172a);
  margin: 0 0 6px;
  text-align: center;
}

.welcome-subtitle {
  font-size: 13px;
  color: var(--el-text-color-secondary, #64748b);
  margin: 0 0 32px;
  text-align: center;
  line-height: 1.5;
}

.use-cases {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.use-case-btn {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 12px 14px;
  text-align: left;
  border: 1px solid var(--el-border-color, #e2e8f0);
  border-radius: 10px;
  background: var(--el-fill-color, #fff);
  cursor: pointer;
  transition: all 0.15s ease;
}

.use-case-btn:hover {
  border-color: var(--el-color-primary-light-5, #93c5fd);
  background: var(--el-color-primary-light-9, #eff6ff);
}

.use-case-btn:active {
  transform: scale(0.99);
}

.uc-number {
  font-family: 'Fira Code', monospace;
  font-size: 11px;
  font-weight: 600;
  color: var(--el-color-primary, #2563eb);
  min-width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  background: var(--el-color-primary-light-9, #eff6ff);
  flex-shrink: 0;
}

.uc-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.uc-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-primary, #0f172a);
}

.uc-desc {
  font-size: 11px;
  color: var(--el-text-color-secondary, #64748b);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.uc-arrow {
  color: var(--el-text-color-disabled, #cbd5e1);
  flex-shrink: 0;
  transition: color 0.15s, transform 0.15s;
}

.use-case-btn:hover .uc-arrow {
  color: var(--el-color-primary, #2563eb);
  transform: translateX(2px);
}

/* Token bar */
.token-bar {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 16px;
  font-size: 11px;
  color: var(--el-text-color-disabled, #94a3b8);
  border-top: 1px solid var(--el-border-color-light, #f1f5f9);
  justify-content: flex-end;
}

.token-value {
  font-family: 'Fira Code', monospace;
  font-weight: 600;
  color: var(--el-text-color-secondary, #64748b);
}

/* Error bar */
.error-bar {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 14px;
  font-size: 12px;
  color: var(--el-color-danger, #dc2626);
  border-top: 1px solid var(--el-color-danger-light-7, #fecaca);
  background: var(--el-color-danger-light-9, #fef2f2);
}
</style>

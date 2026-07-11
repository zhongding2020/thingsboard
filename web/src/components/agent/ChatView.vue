<template>
  <div class="chat-view">
    <!-- Messages area -->
    <div ref="msgRef" class="messages-area">
      <!-- Welcome screen -->
      <div v-if="!messages.length" class="welcome">
        <h1 class="welcome-title">工艺参数在线分析与调优</h1>
        <p class="welcome-subtitle">AI 驱动的制造过程优化助手</p>

        <div class="use-cases">
          <button
            v-for="(uc, i) in useCases"
            :key="i"
            class="use-case-btn"
            @click="send(uc.prompt)"
          >
            <span class="uc-arrow">➤</span>
            <span class="uc-title">{{ uc.title }}</span>
          </button>
        </div>
      </div>

      <!-- Messages -->
      <div v-if="messages.length" class="msg-list">
        <MessageCard
          v-for="(msg, i) in messages"
          :key="msg.id || i"
          :msg="msg"
          :loading="(status === 'submitted' || status === 'streaming') && i === messages.length - 1 && msg.role === 'assistant'"
          @resolve-action="resolveAction"
        />
      </div>
    </div>

    <!-- Error bar -->
    <div v-if="error" class="error-bar">{{ error }}</div>

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
} = useAgentChat(props.processType || 'injection_molding')

const msgRef = ref<HTMLDivElement>()

const useCases = [
  { title: '分析温度参数与质量指标的关联关系', prompt: '帮我分析当前设备最近100条数据的相关性，重点关注温度参数与质量指标的关联' },
  { title: '识别影响成品率的关键工艺参数', prompt: '对设备数据做特征重要性分析，识别影响成品率的关键工艺参数' },
  { title: '对生产工艺做完整过程能力分析', prompt: '对注塑成型工艺做完整过程能力分析，包括控制图和Cp/Cpk' },
  { title: '推荐最优的工艺参数组合', prompt: '根据最近一周的生产数据，推荐最优的工艺参数组合' },
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
.chat-view { display: flex; flex-direction: column; height: 100%; }
.messages-area { flex: 1; overflow-y: auto; padding: 16px; }
.msg-list { display: flex; flex-direction: column; gap: 4px; }

/* Welcome */
.welcome { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 40px 16px; }
.welcome-title { font-size: 22px; font-weight: 600; color: #374151; margin: 0 0 4px; }
.welcome-subtitle { font-size: 14px; color: #9ca3af; margin: 0 0 28px; }
.use-cases { width: 100%; max-width: 480px; border: 1px solid #e5e7eb; border-radius: 12px; overflow: hidden; }
.use-case-btn { display: flex; align-items: center; gap: 10px; width: 100%; padding: 12px 16px; text-align: left; border: none; border-bottom: 1px solid #f3f4f6; background: transparent; cursor: pointer; transition: background 0.15s; }
.use-case-btn:last-child { border-bottom: none; }
.use-case-btn:hover { background: #eff6ff; }
.uc-arrow { font-size: 10px; color: #d1d5db; flex-shrink: 0; }
.uc-title { font-size: 13px; color: #4b5563; }

/* Error */
.error-bar { padding: 6px 14px; font-size: 12px; color: #ef4444; border-top: 1px solid #fce7f3; background: #fef2f2; }
</style>

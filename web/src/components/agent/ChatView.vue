<template>
  <div class="agent-messages" ref="msgRef">
    <div v-if="!messages.length && !loading" class="agent-welcome">
      <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" style="color:#6366f1;opacity:0.4;margin-bottom:12px"><path d="M12 2l2.8 6L21 9l-4.5 3.8L17.8 19 12 16l-5.8 3 1.3-6.2L3 9l6.2-1z"/></svg>
      <p>可分析数据、优化参数、监控产线</p>
    </div>
    <ChatBubble
      v-for="(msg, i) in messages" :key="i"
      :msg="msg" :msgIndex="i" :isStreaming="loading && i === messages.length - 1"
      @copy="copyMsg" @regenerate="onRegenerate"
    />
    <ChatLoading v-if="loading" />
    <ChatSuggestions v-if="suggestions.length && !loading" :questions="suggestions" @select="onSuggestion" />
  </div>
  <div v-if="error" class="agent-error">{{ error }}</div>
  <div ref="inputArea">
    <PhaseIndicator v-if="workflowPhase" :phase="workflowPhase" />
    <ChatInput :disabled="loading" @send="onSend" @upload="onUpload" @startWorkflow="onStartWorkflow" />
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import ChatBubble from './ChatBubble.vue'
import ChatLoading from './ChatLoading.vue'
import ChatSuggestions from './ChatSuggestions.vue'
import ChatInput from './ChatInput.vue'
import PhaseIndicator from './PhaseIndicator.vue'
import { useChatMessages } from '@/composables/useChatMessages'
import { useChatStream } from '@/composables/useChatStream'
import { useChatSession } from '@/composables/useChatSession'
import { useFileUpload } from '@/composables/useFileUpload'

const { sessionId, createNewSession } = useChatSession()
const { messages, suggestions, workflowPhase, addUserMessage, addAssistantPlaceholder, appendDelta, addToolCall, addToolResult, addTrace, copyMessage, regenerateMessage } = useChatMessages()
const { loading, error, sendAndStream } = useChatStream()
const { upload } = useFileUpload()

const msgRef = ref<HTMLDivElement>()

function scrollBottom() {
  nextTick(() => { if (msgRef.value) msgRef.value.scrollTop = msgRef.value.scrollHeight })
}

function makeCallbacks(assistantIdx: number) {
  return {
    onDelta: (delta: string) => { appendDelta(assistantIdx, delta); scrollBottom() },
    onToolCall: (name: string, args: any) => { addToolCall(assistantIdx, name, args); scrollBottom() },
    onToolResult: (name: string, data: string, durationMs: number) => { addToolResult(assistantIdx, name, data, durationMs); scrollBottom() },
    onDone: () => { scrollBottom() },
    onError: () => { scrollBottom() },
    onSuggestions: (questions: string[]) => { suggestions.value = questions },
    onTrace: (node: string, text: string) => { addTrace(assistantIdx, node, text); scrollBottom() },
    onPhase: (phase: string) => { workflowPhase.value = phase },
  }
}

async function onSend(text: string) {
  addUserMessage(text)
  scrollBottom()
  suggestions.value = []

  if (!sessionId.value) {
    await createNewSession()
    sessionStorage.setItem('opencode-session', sessionId.value)
  }

  const assistantIdx = addAssistantPlaceholder()
  scrollBottom()

  await sendAndStream(sessionId.value, text, makeCallbacks(assistantIdx))
}

async function onUpload(file: File) {
  if (!sessionId.value) {
    await createNewSession()
    sessionStorage.setItem('opencode-session', sessionId.value)
  }
  await upload(file, {
    onSuccess: (datasetId: string, features: string[], targets: string[]) => {
      addUserMessage('上传文件: ' + file.name)
      loading.value = true
      scrollBottom()
      suggestions.value = []

      const assistantIdx = addAssistantPlaceholder()
      scrollBottom()

      const msg = `对数据集 ${datasetId} 做完整相关性分析，包含相关性热力图。特征字段: ${features.join(',')}，目标字段: ${targets.join(',')}`
      sendAndStream(sessionId.value, msg, makeCallbacks(assistantIdx))
    },
    onError: (msg: string) => { error.value = msg },
  })
}

function onRegenerate(idx: number) {
  if (loading.value) return
  const text = regenerateMessage(idx)
  if (text) onSend(text)
}

function onSuggestion(q: string) {
  onSend(q)
}

function copyMsg(msg: any) {
  copyMessage(msg)
}

function onStartWorkflow() {
  onSend('__start_workflow__')
}
</script>

<style scoped>
.agent-messages { flex: 1; overflow-y: auto; padding: 14px; display: flex; flex-direction: column; gap: 10px; }
.agent-error { padding: 6px 14px; font-size: 12px; color: var(--el-color-danger); border-top: 1px solid var(--el-border-color-light); }
.agent-welcome { text-align: center; padding: 60px 24px; color: var(--el-text-color-secondary); }
.agent-welcome p { margin: 4px 0; font-size: 14px; }
</style>

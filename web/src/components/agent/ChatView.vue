<template>
  <div class="agent-messages" ref="msgRef">
    <div v-if="!messages.length && !loading" class="agent-welcome">
      <div class="welcome-content" v-html="welcomeHtml" />
    </div>
    <ChatBubble
      v-for="(msg, i) in messages" :key="i"
      :msg="msg" :msgIndex="i" :isStreaming="loading && i === messages.length - 1"
      @copy="copyMsg" @regenerate="onRegenerate"
    />
    <details v-if="thinkingText" class="thinking-box" :open="loading">
      <summary>{{ loading ? '思考中...' : '思考过程' }}</summary>
      <div class="thinking-content">{{ thinkingText }}</div>
    </details>
    <ChatLoading v-if="loading" />
    <ChatSuggestions v-if="suggestions.length && !loading" :questions="suggestions" @select="onSuggestion" />
  </div>
  <div v-if="error" class="agent-error">{{ error }}</div>
  <div ref="inputArea">
    <PhaseIndicator v-if="workflowPhase" :phase="workflowPhase" />
    <ChatInput :disabled="loading" @send="onSend" @upload="onUpload" @startWorkflow="onStartWorkflow" @stop="cancel()" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import { marked } from 'marked'
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
const { loading, error, sendAndStream, cancel } = useChatStream()
const { upload } = useFileUpload()

const msgRef = ref<HTMLDivElement>()
const thinkingText = ref('')

const welcomeMd = `## 🤖 工艺参数分析助手

输入 \`?\` 随时查看此帮助。支持 **8 种** 制造工艺的智能化分析。

| 功能 | 功能说明 | 示例 |
|------|----------|------|
| 📊 数据画像 | 自动统计均值/标准差/极值/异常值 | 「分析D1设备的数据画像」 |
| 🔗 相关性分析 | Pearson/Spearman 系数 + 热力图 | 「分析温度与剪切强度的相关性」 |
| 📈 回归建模 | Linear/PLS 回归，R²/RMSE/系数 | 「建立固化温度、时间对强度的回归」 |
| ⭐ 特征重要性 | 随机森林排序关键影响因子 | 「哪些参数对气泡率影响最大」 |
| 📉 SPC 监控 | I-MR 控制图、Cp/Cpk 过程能力 | 「查看 wave-solder-004 的 SPC」 |
| 🧪 DOE 实验 | 全因子/Box-Behnken/田口 + ANOVA | 「为固化工艺设计 Box-Behnken 实验」 |
| 🎯 参数推荐 | 网格/LHS 搜索 + 工艺规则校验 | 「推荐提高剪切强度的参数」 |
| 🏭 系统查询 | 产线/设备/参数集/平台统计 | 「系统有哪些产线」 |
| 🔍 产品追溯 | 按条码追溯完整生产链路 | 「追溯条码 B001」 |
| 🔄 工艺调优 | Define→Explore→Analyze→Optimize→Verify | 输入「优化剪切强度」启动 |

点击下方 ⭐ **工艺调优** 开始引导式参数优化。`

const welcomeHtml = computed(() => marked.parse(welcomeMd, { breaks: true, gfm: true }) as string)

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
    onThinking: (type: string, text?: string) => {
      if (type === 'thinking.start') { thinkingText.value = '' }
      else if (type === 'thinking.delta') { thinkingText.value += (text || ''); scrollBottom() }
      else if (type === 'thinking.done') { /* keep visible */ }
    },
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
.agent-welcome { padding: 20px 18px; color: var(--el-text-color-secondary); }
.agent-welcome :deep(h2) { font-size: 16px; color: #6366f1; margin: 0 0 8px; }
.agent-welcome :deep(p) { margin: 4px 0; font-size: 13px; }
.agent-welcome :deep(table) { border-collapse: collapse; width: 100%; font-size: 12px; margin: 8px 0; }
.agent-welcome :deep(th), .agent-welcome :deep(td) { border: 1px solid var(--el-border-color-light); padding: 4px 8px; text-align: left; }
.agent-welcome :deep(th) { background: var(--el-fill-color); }
.agent-welcome :deep(code) { background: var(--el-fill-color-dark); padding: 1px 5px; border-radius: 3px; font-size: 12px; }
.thinking-box { margin: 4px 14px; border: 1px solid var(--el-color-info-light-5); border-radius: 8px; padding: 6px 10px; font-size: 12px; background: var(--el-color-info-light-9); }
.thinking-box summary { cursor: pointer; color: var(--el-color-info); font-weight: 500; }
.thinking-box[open] summary { margin-bottom: 4px; }
.thinking-content { color: var(--el-text-color-secondary); line-height: 1.5; white-space: pre-wrap; }
</style>

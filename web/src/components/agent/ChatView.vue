<template>
  <div class="flex flex-col h-full bg-white dark:bg-gray-950">
    <!-- Header toolbar -->
    <div class="flex items-center justify-between px-3 py-1.5 border-b border-gray-200 dark:border-gray-800">
      <span class="text-xs font-medium text-gray-500 dark:text-gray-400">对话</span>
      <div class="flex items-center gap-0.5">
        <!-- Files toggle -->
        <button
          class="flex items-center gap-1 px-2 py-1 text-[11px] rounded border-none cursor-pointer transition-colors"
          :class="activePanel === 'files'
            ? 'bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400'
            : 'bg-transparent text-gray-400 hover:text-gray-600 dark:hover:text-gray-300'"
          @click="activePanel = activePanel === 'files' ? null : 'files'"
        >📁 文件</button>
        <!-- Todos toggle -->
        <button
          class="flex items-center gap-1 px-2 py-1 text-[11px] rounded border-none cursor-pointer transition-colors"
          :class="activePanel === 'todos'
            ? 'bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400'
            : 'bg-transparent text-gray-400 hover:text-gray-600 dark:hover:text-gray-300'"
          @click="activePanel = activePanel === 'todos' ? null : 'todos'"
        >
          ✅ 待办
          <span
            v-if="allTodos.length > 0"
            class="text-[10px] px-1 rounded-full"
            :class="activePanel === 'todos'
              ? 'bg-blue-200 dark:bg-blue-800'
              : 'bg-gray-100 dark:bg-gray-800'"
          >{{ doneTodoCount }}/{{ allTodos.length }}</span>
        </button>
        <!-- Debug toggle -->
        <button
          class="flex items-center gap-1 px-2 py-1 text-[11px] rounded border-none cursor-pointer transition-colors"
          :class="showDebug
            ? 'bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400'
            : 'bg-transparent text-gray-400 hover:text-gray-600 dark:hover:text-gray-300'"
          @click="showDebug = !showDebug"
        >🐛 调试</button>
      </div>
    </div>

    <!-- Main row: chat + optional panel -->
    <div class="flex-1 flex overflow-hidden">
      <!-- Chat column -->
      <div class="flex-1 flex flex-col min-w-0">
        <!-- Messages area -->
        <div ref="msgRef" class="flex-1 overflow-y-auto px-4 py-3 flex flex-col gap-3">
          <!-- Welcome screen — agent feature intro -->
          <div
            v-if="!msgs.length && !loading"
            class="flex-1 flex items-center justify-center px-4 py-6 overflow-y-auto"
          >
            <div class="max-w-lg w-full">
              <!-- Hero -->
              <h1 class="text-center text-xl font-semibold text-slate-700 dark:text-slate-200 mb-1">
                工艺参数在线分析与调优
              </h1>
              <p class="text-center text-sm text-slate-400 dark:text-slate-500 mb-6">
                AI 驱动的制造过程优化助手
              </p>

              <!-- Optimization workflow (wizard steps) -->
              <div class="mb-5 rounded-xl border border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-950/30 p-5">
                <p class="text-sm font-semibold text-blue-700 dark:text-blue-300 mb-4 flex items-center gap-1.5">
                  <span>🔄</span> 工艺参数优化流程
                </p>
                <!-- 5-step indicator -->
                <div class="flex items-center justify-between mb-4 px-1">
                  <template v-for="(step, i) in workflowSteps" :key="step.name">
                    <div
                      class="flex flex-col items-center gap-1.5 cursor-pointer group/step"
                      @mouseenter="hoveredStep = i"
                    >
                      <span
                        class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-all duration-200"
                        :class="hoveredStep === i
                          ? 'bg-blue-600 dark:bg-blue-500 border-blue-600 dark:border-blue-500 text-white scale-110 shadow-md shadow-blue-500/25'
                          : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-600 text-slate-400 dark:text-slate-500 group-hover/step:border-blue-400 group-hover/step:text-blue-500'"
                      >{{ i + 1 }}</span>
                      <span
                        class="text-[11px] font-medium transition-colors duration-200"
                        :class="hoveredStep === i
                          ? 'text-blue-600 dark:text-blue-400'
                          : 'text-slate-400 dark:text-slate-500 group-hover/step:text-slate-500 dark:group-hover/step:text-slate-300'"
                      >{{ step.name }}</span>
                    </div>
                    <!-- connector line -->
                    <div
                      v-if="i < workflowSteps.length - 1"
                      class="flex-1 h-0.5 mx-1 -mt-3 rounded transition-colors duration-200"
                      :class="hoveredStep > i || (hoveredStep === 0 && i === 0)
                        ? 'bg-blue-400 dark:bg-blue-500'
                        : 'bg-slate-200 dark:bg-slate-700'"
                    />
                  </template>
                </div>
                <!-- Step description (reacts to hover) + CTA -->
                <div class="min-h-[36px] mb-3 transition-all duration-200">
                  <p class="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                    <span class="inline-block mr-1.5 px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-100 dark:bg-blue-900/60 text-blue-600 dark:text-blue-400 align-middle">
                      {{ hoveredStep + 1 }}
                    </span>
                    <span class="align-middle">{{ workflowSteps[hoveredStep].name }} — {{ workflowSteps[hoveredStep].desc }}</span>
                  </p>
                </div>
                <button
                  class="w-full flex items-center justify-center gap-1.5 py-2.5 rounded-lg border-none cursor-pointer text-sm font-medium transition-all duration-200 bg-blue-600 dark:bg-blue-500 text-white hover:bg-blue-700 dark:hover:bg-blue-400 hover:shadow-md"
                  @click="onSend(workflowStartPrompt)"
                >
                  开始优化流程
                  <span>→</span>
                </button>
              </div>

              <!-- Feature cards (2x2 grid) -->
              <div class="grid grid-cols-2 gap-3 mb-5">
                <div
                  v-for="f in features"
                  :key="f.title"
                  class="rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 p-3.5 cursor-pointer transition-all duration-200 hover:border-blue-300 dark:hover:border-blue-700 hover:bg-blue-50/50 dark:hover:bg-blue-950/40 hover:shadow-md hover:-translate-y-0.5"
                  @click="onSend(f.prompt)"
                >
                  <div class="flex items-center gap-2 mb-2">
                    <span class="text-lg">{{ f.icon }}</span>
                    <span class="text-sm font-semibold text-slate-700 dark:text-slate-200">{{ f.title }}</span>
                  </div>
                  <p class="text-xs text-slate-500 dark:text-slate-400 mb-2.5 leading-relaxed">{{ f.desc }}</p>
                  <div class="flex flex-wrap gap-1">
                    <span
                      v-for="t in f.tags"
                      :key="t"
                      class="text-[10px] px-1.5 py-0.5 rounded bg-white dark:bg-slate-800 text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-slate-700"
                    >{{ t }}</span>
                  </div>
                </div>
              </div>

              <!-- Use cases -->
              <div class="mb-4">
                <p class="text-sm font-medium text-slate-500 dark:text-slate-400 mb-2.5 flex items-center gap-1">
                  <span>💡</span> 使用案例
                </p>
                <div class="rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden divide-y divide-slate-100 dark:divide-slate-800">
                  <button
                    v-for="(uc, i) in useCases"
                    :key="i"
                    class="w-full flex items-center gap-2.5 px-3.5 py-3 text-left hover:bg-blue-50 dark:hover:bg-blue-950/40 transition-colors group cursor-pointer border-none bg-transparent"
                    @click="onSend(uc.prompt)"
                  >
                    <span class="text-xs text-slate-300 dark:text-slate-600 group-hover:text-blue-400 transition-colors flex-shrink-0">➤</span>
                    <span class="text-sm text-slate-600 dark:text-slate-300 group-hover:text-blue-600 dark:group-hover:text-blue-300 transition-colors leading-relaxed">{{ uc.title }}</span>
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- Message cards -->
          <MessageCard
            v-for="(msg, i) in msgs"
            :key="i"
            :msg="msg"
            :isStreaming="loading && i === msgs.length - 1 && msg.role === 'assistant'"
            @copy="copyMsg(msg)"
            @regenerate="onRegenerate(i)"
            @resolveAction="resolveAction"
          />

          <!-- Loading dots (thinking phase with no content yet) -->
          <div
            v-if="loading && lastMsg?.role === 'assistant' && !lastMsg?.content && !lastMsg?.toolCalls?.length"
            class="flex items-center gap-1.5 px-4 py-2"
          >
            <span class="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 0ms" />
            <span class="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 150ms" />
            <span class="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 300ms" />
          </div>

          <!-- Suggestions -->
          <div v-if="suggestions.length && !loading" class="flex flex-wrap gap-2">
            <button
              v-for="(q, i) in suggestions"
              :key="i"
              class="px-3 py-1.5 text-xs rounded-full border border-gray-200 dark:border-gray-700 bg-transparent text-gray-500 dark:text-gray-400 hover:border-blue-300 hover:text-blue-500 cursor-pointer transition-colors"
              @click="onSend(q)"
            >{{ q }}</button>
          </div>
        </div>

        <!-- Error bar -->
        <div
          v-if="error"
          class="px-4 py-1.5 text-xs text-red-500 border-t border-red-100 dark:border-red-900"
        >{{ error }}</div>

        <!-- Phase indicator -->
        <div
          v-if="currentPhase"
          class="px-4 py-1.5 text-xs text-blue-500 border-t border-blue-100 dark:border-blue-900 bg-blue-50 dark:bg-blue-950"
        >
          📍 当前阶段: {{ currentPhase }}
        </div>

        <!-- Debug panel -->
        <DebugPanel
          v-if="showDebug"
          :events="debugEvents"
          @clear="debugEvents.length = 0"
        />

        <!-- Input -->
        <ChatInput
          :disabled="loading"
          @send="onSend"
          @upload="onUpload"
          @startWorkflow="onStartWorkflow"
          @stop="cancel"
        />
      </div>

      <!-- Right panel -->
      <Transition name="slide-right">
        <div
          v-if="activePanel"
          class="w-80 flex-shrink-0 overflow-hidden border-l border-gray-200 dark:border-gray-800"
        >
          <FilesystemDrawer
            v-if="activePanel === 'files'"
            :messages="msgs"
            @close="activePanel = null"
          />
          <TodoDrawer
            v-if="activePanel === 'todos'"
            :todos="allTodos"
            @close="activePanel = null"
          />
        </div>
      </Transition>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, shallowRef, nextTick } from 'vue'
import MessageCard from './MessageCard.vue'
import ChatInput from './ChatInput.vue'
import FilesystemDrawer from './panels/FilesystemDrawer.vue'
import TodoDrawer from './panels/TodoDrawer.vue'
import DebugPanel from './panels/DebugPanel.vue'
import { useAgentStream } from '@/composables/useAgentStream'
import { useChatSession } from '@/composables/useChatSession'
import { useFileUpload } from '@/composables/useFileUpload'
import type { ChatMessage, ActionResponse, ToolCall, SubagentState, InteractiveAction } from '@/composables/useAgentStream'

const { sessionId, createNewSession } = useChatSession()
const { upload } = useFileUpload()

const msgRef = ref<HTMLDivElement>()

// ---------------------------------------------------------------------------
// Lazy stream initialization — avoids the sessionId reactivity bug.
// useAgentStream captures sessionId by VALUE in its closure. If called with
// an empty string, send() will early-return.  We defer creation until the
// session is real, and wrap the return value in a shallowRef so computed
// accessors always read from the *current* stream's reactive refs.
// ---------------------------------------------------------------------------
const streamRef = shallowRef<ReturnType<typeof useAgentStream> | null>(null)

/** Ensure a stream exists for the current session, creating one if needed. */
function ensureStream(): ReturnType<typeof useAgentStream> {
  if (!streamRef.value) {
    streamRef.value = useAgentStream(sessionId.value)
  }
  return streamRef.value
}

// Computed accessors — proxy through to the current stream's reactive refs.
// When streamRef is reassigned, these automatically re-wire to the new stream.
const msgs = computed(() => streamRef.value?.messages.value ?? [])
const loading = computed(() => streamRef.value?.loading.value ?? false)
const error = computed(() => streamRef.value?.error.value ?? '')
const suggestions = computed(() => streamRef.value?.suggestions.value ?? [])
const currentPhase = computed(() => streamRef.value?.currentPhase.value ?? '')
const allTodos = computed(() => streamRef.value?.todos.value ?? [])
const doneTodoCount = computed(() => allTodos.value.filter((t) => t.done).length)
const debugEvents = computed(() => streamRef.value?.debugEvents.value ?? [])

// ---------------------------------------------------------------------------
// Right panel state
// ---------------------------------------------------------------------------
const activePanel = ref<'files' | 'todos' | null>(null)
const showDebug = ref(false)

// ---------------------------------------------------------------------------
// Process types for welcome cards
// ---------------------------------------------------------------------------
// Process types retained for future use
const _processTypes = [
  { type: 'adhesive_curing', name: '点胶固化', en: 'Adhesive Curing', icon: '🔬', bg: 'bg-cyan-100 dark:bg-cyan-900/40 text-cyan-700 dark:text-cyan-300' },
  { type: 'injection_molding', name: '注塑成型', en: 'Injection Molding', icon: '⚙️', bg: 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300' },
  { type: 'die_casting', name: '压铸', en: 'Die Casting', icon: '🔥', bg: 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300' },
  { type: 'cnc_machining', name: 'CNC加工', en: 'CNC Machining', icon: '🪚', bg: 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300' },
  { type: 'reflow_soldering', name: '回流焊', en: 'Reflow Soldering', icon: '🌊', bg: 'bg-sky-100 dark:bg-sky-900/40 text-sky-700 dark:text-sky-300' },
  { type: 'heat_treatment', name: '热处理', en: 'Heat Treatment', icon: '🌡️', bg: 'bg-orange-100 dark:bg-orange-900/40 text-orange-700 dark:text-orange-300' },
  { type: 'welding', name: '焊接', en: 'Welding', icon: '⚡', bg: 'bg-yellow-100 dark:bg-yellow-900/40 text-yellow-700 dark:text-yellow-300' },
  { type: 'powder_coating', name: '粉末涂装', en: 'Powder Coating', icon: '🎨', bg: 'bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300' },
] as const
void _processTypes

// ---------------------------------------------------------------------------
// Welcome screen — optimization workflow steps, feature cards & use cases
// ---------------------------------------------------------------------------
const hoveredStep = ref(0)

const workflowSteps = [
  { name: '定义', desc: '首先明确优化目标：选择产线、设备和需要优化的质量指标，确定参数搜索范围', active: true },
  { name: '探索', desc: '对数据进行统计画像，了解数据分布特征，发现异常值和潜在规律', active: true },
  { name: '分析', desc: '深入分析：相关性矩阵 → 回归建模 → 特征重要性排序 → SPC 过程能力评估', active: true },
  { name: '优化', desc: '基于分析结果，结合约束规则推荐最优参数组合，并通过多目标优化验证', active: true },
  { name: '验证', desc: '生成分析报告，对比优化前后效果，可将推荐参数保存为参数集草案', active: true },
] as const

const workflowStartPrompt =
  '请启动工艺参数优化流程（define → explore → analyze → optimize → validate）。首先进入 Define 阶段：询问我要优化的产线、设备和目标质量指标。'

const features = [
  {
    icon: '📊',
    title: '数据分析',
    desc: '多维度统计分析，发现数据中的规律与异常',
    tags: ['相关性', '回归', 'SPC', '特征重要性'],
    prompt: '请帮我分析最近的生产数据，包括相关性分析和特征重要性排序',
  },
  {
    icon: '🎯',
    title: '智能优化',
    desc: '基于历史数据推荐最优工艺参数组合',
    tags: ['参数推荐', '多目标优化', 'Pareto', '报告'],
    prompt: '请根据最近的生产数据推荐最优工艺参数组合',
  },
  {
    icon: '🔍',
    title: '追溯监控',
    desc: '产品质量追溯与产线实时状态监控',
    tags: ['产品追溯', '产线SPC', '统计概览'],
    prompt: '请对当前产线做一次完整的SPC监控总览',
  },
  {
    icon: '🧪',
    title: '实验设计',
    desc: '科学的实验方案设计与结果分析',
    tags: ['DOE', 'ANOVA', '参数管理'],
    prompt: '请帮我设计一个工艺参数优化实验方案',
  },
] as const

const useCases = [
  {
    title: '分析温度参数与质量指标的关联关系',
    prompt: '帮我分析当前设备最近100条数据的相关性，重点关注温度参数与质量指标的关联',
  },
  {
    title: '识别影响成品率的关键工艺参数',
    prompt: '对设备数据做特征重要性分析，识别影响成品率的关键工艺参数',
  },
  {
    title: '对生产工艺做完整过程能力分析',
    prompt: '对注塑成型工艺做完整过程能力分析，包括控制图和Cp/Cpk',
  },
  {
    title: '推荐最优的工艺参数组合',
    prompt: '根据最近一周的生产数据，推荐最优的工艺参数组合',
  },
] as const

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const lastMsg = computed(() => {
  const arr = msgs.value
  for (let i = arr.length - 1; i >= 0; i--) {
    if (arr[i].role === 'assistant') return arr[i]
  }
  return null
})

function scrollBottom() {
  nextTick(() => {
    if (msgRef.value) msgRef.value.scrollTop = msgRef.value.scrollHeight
  })
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------
async function onSend(text: string) {
  // Ensure session exists
  if (!sessionId.value) {
    await createNewSession()
    sessionStorage.setItem('opencode-session', sessionId.value)
  }

  // Lazily create stream now that we have a real sessionId.
  // If streamRef.value already exists (created by a previous send), reuse it;
  // the send() closure captured the sessionId at creation time, which is already valid.
  const stream = ensureStream()
  await stream.send(text)
  scrollBottom()
}

function cancel() {
  streamRef.value?.cancel()
}

function onStartWorkflow() {
  onSend('__start_workflow__')
}

async function onUpload(file: File) {
  if (!sessionId.value) {
    await createNewSession()
    sessionStorage.setItem('opencode-session', sessionId.value)
  }
  await upload(file, {
    onSuccess: (datasetId, features, targets) => {
      onSend(
        `对数据集 ${datasetId} 做完整相关性分析，包含相关性热力图。特征字段: ${features.join(',')}，目标字段: ${targets.join(',')}`,
      )
    },
    onError: (msg) => {
      const stream = ensureStream()
      stream.error.value = msg
    },
  })
}

function onRegenerate(idx: number) {
  if (loading.value) return
  const stream = streamRef.value
  if (!stream) return
  const arr = stream.messages.value
  const userMsg = arr[idx - 1]
  if (!userMsg || userMsg.role !== 'user') return
  // Remove the user message and the assistant response that followed it
  arr.splice(idx - 1, 2)
  onSend(userMsg.content)
}

function copyMsg(msg: ChatMessage) {
  const text = msg.content || ''
  navigator.clipboard.writeText(text).catch(() => {})
}

async function resolveAction(msg: ChatMessage, actionId: string, value: unknown) {
  // Mark the action as resolving
  const action = msg.actions?.find(a => a.id === actionId)
  if (!action) return
  action.status = 'submitting'

  // Build action response
  const actionResponse: ActionResponse = {
    action_id: actionId,
    type: action.type,
    value,
  }

  // Store resolved label for display
  if (action.type === 'select') {
    action._resolvedLabel = (value as { label: string }).label
  } else if (action.type === 'multi_select') {
    const v = value as { values: { label: string }[] }
    action._resolvedLabel = v.values.map(x => x.label).join('、')
  } else if (action.type === 'confirm') {
    action._resolvedValue = (value as { confirmed: boolean }).confirmed
  } else if (action.type === 'cascader') {
    const v = value as Record<string, { label: string }>
    action._resolvedLabel = Object.values(v).map(x => x.label).join(' → ')
  } else if (action.type === 'input') {
    action._resolvedLabel = (value as { value: string }).value
  }

  // Ensure session exists
  if (!sessionId.value) {
    await createNewSession()
    sessionStorage.setItem('opencode-session', sessionId.value)
  }

  // Send via POST /chat with action_responses
  try {
    const API_URL = import.meta.env.DEV ? '/api/v1/agent' : 'http://localhost:8000/api/v1/agent'
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 30000)
    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        signal: controller.signal,
        headers: { 'Content-Type': 'application/json', 'X-User': 'anonymous' },
        body: JSON.stringify({
          session_id: sessionId.value,
          text: '',
          action_responses: [actionResponse],
        }),
      })
      if (!res.ok) throw new Error(`${res.status}`)
    } finally {
      clearTimeout(timeout)
    }

    action.status = 'resolved'

    // Trigger SSE to get agent's follow-up response
    const stream = ensureStream()
    stream.loading.value = true

    const res = await fetch(
      `${API_URL}/chat/${encodeURIComponent(sessionId.value)}/events`,
      { headers: { 'X-User': 'anonymous' } }
    )
    if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)

    // Add placeholder assistant message for the response
    const assistantMsg: ChatMessage = {
      role: 'assistant',
      content: '',
      toolCalls: [],
      subagents: [],
    }
    stream.messages.value.push(assistantMsg)

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let thinkingBuf = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed.startsWith('data: ')) continue
        try {
          const event = JSON.parse(trimmed.slice(6))
          stream.debugEvents.value.push({
            type: event.type,
            name: event.node || event.name || event.phase || undefined,
            timestamp: Date.now(),
            payload: event,
          })
          switch (event.type) {
            case 'message.delta':
              assistantMsg.content += event.text || ''
              break

            case 'tool.call': {
              const tc: ToolCall = {
                name: event.node || event.name,
                args: event.args || {},
                status: 'pending',
              }
              assistantMsg.toolCalls = [...(assistantMsg.toolCalls || []), tc]
              break
            }

            case 'tool.result': {
              const tcs = assistantMsg.toolCalls || []
              const last = [...tcs].reverse().find(t => t.name === (event.node || event.name) && t.status === 'pending')
              if (last) {
                last.result = event.data || ''
                last.durationMs = event.duration_ms || 0
                last.status = 'done'
              }
              break
            }

            case 'interactive.prompt': {
              const action: InteractiveAction = {
                ...event.action,
                status: 'pending',
              }
              assistantMsg.actions = [...(assistantMsg.actions || []), action]
              break
            }

            case 'subagent.start': {
              const sa: SubagentState = {
                name: event.node || event.name,
                content: '',
                status: 'running',
                open: true,
              }
              assistantMsg.subagents = [...(assistantMsg.subagents || []), sa]
              break
            }

            case 'subagent.delta': {
              const sa = (assistantMsg.subagents || []).find(s => s.name === (event.node || event.name) && s.status === 'running')
              if (sa) sa.content += event.text || ''
              break
            }

            case 'subagent.end': {
              const sa = (assistantMsg.subagents || []).find(s => s.name === (event.node || event.name) && s.status === 'running')
              if (sa) sa.status = 'done'
              break
            }

            case 'todo.update':
              stream.todos.value = event.todos || []
              break

            case 'thinking.start':
              thinkingBuf = ''
              break
            case 'thinking.delta':
              thinkingBuf += event.text || ''
              break
            case 'thinking.done':
              if (thinkingBuf) assistantMsg.thinking = thinkingBuf
              break

            case 'phase.change':
              stream.currentPhase.value = event.phase
              break

            case 'suggestions':
              stream.suggestions.value = event.questions || []
              break

            case 'session.status':
              if (event.status === 'idle') {
                stream.loading.value = false
              }
              break

            case 'error':
              stream.error.value = event.message || ''
              stream.loading.value = false
              break
          }
        } catch { /* skip malformed */ }
      }
    }
    stream.loading.value = false
    scrollBottom()
  } catch (e: unknown) {
    action.status = 'rejected'
    if ((e as Error).name !== 'AbortError') {
      if (streamRef.value) {
        streamRef.value.error.value = (e as Error).message || '操作失败'
      }
    }
  }
}
</script>

<style scoped>
/* Slide-in from right transition for the panel drawer */
.slide-right-enter-active,
.slide-right-leave-active {
  transition: all 0.25s ease;
}
.slide-right-enter-from,
.slide-right-leave-to {
  width: 0 !important;
  opacity: 0;
}
</style>

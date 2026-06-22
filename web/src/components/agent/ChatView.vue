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
          <!-- Welcome screen — process type cards -->
          <div
            v-if="!msgs.length && !loading"
            class="flex-1 flex items-center justify-center px-6"
          >
            <div class="max-w-xl w-full">
              <h1 class="text-base font-semibold text-slate-700 dark:text-slate-200 text-center mb-1">工艺参数分析助手</h1>
              <p class="text-xs text-slate-400 dark:text-slate-500 text-center mb-5">选择一个工艺类型开始分析，或直接输入问题</p>
              <div class="grid grid-cols-2 gap-2">
                <button
                  v-for="pt in processTypes" :key="pt.type"
                  class="flex items-center gap-2.5 px-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 hover:border-blue-600 dark:hover:border-blue-400 hover:shadow-sm transition-all text-left group"
                  @click="onSend('分析' + pt.name + '工艺')"
                >
                  <span class="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold flex-shrink-0"
                    :class="pt.bg">{{ pt.icon }}</span>
                  <div class="min-w-0">
                    <div class="text-xs font-medium text-slate-700 dark:text-slate-200 group-hover:text-blue-700 dark:group-hover:text-blue-300 transition-colors">{{ pt.name }}</div>
                    <div class="text-[10px] text-slate-400 dark:text-slate-500 truncate">{{ pt.en }}</div>
                  </div>
                </button>
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
import type { ChatMessage } from '@/composables/useAgentStream'

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
const processTypes = [
  { type: 'adhesive_curing', name: '点胶固化', en: 'Adhesive Curing', icon: '🔬', bg: 'bg-cyan-100 dark:bg-cyan-900/40 text-cyan-700 dark:text-cyan-300' },
  { type: 'injection_molding', name: '注塑成型', en: 'Injection Molding', icon: '⚙️', bg: 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300' },
  { type: 'die_casting', name: '压铸', en: 'Die Casting', icon: '🔥', bg: 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300' },
  { type: 'cnc_machining', name: 'CNC加工', en: 'CNC Machining', icon: '🪚', bg: 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300' },
  { type: 'reflow_soldering', name: '回流焊', en: 'Reflow Soldering', icon: '🌊', bg: 'bg-sky-100 dark:bg-sky-900/40 text-sky-700 dark:text-sky-300' },
  { type: 'heat_treatment', name: '热处理', en: 'Heat Treatment', icon: '🌡️', bg: 'bg-orange-100 dark:bg-orange-900/40 text-orange-700 dark:text-orange-300' },
  { type: 'welding', name: '焊接', en: 'Welding', icon: '⚡', bg: 'bg-yellow-100 dark:bg-yellow-900/40 text-yellow-700 dark:text-yellow-300' },
  { type: 'powder_coating', name: '粉末涂装', en: 'Powder Coating', icon: '🎨', bg: 'bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300' },
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

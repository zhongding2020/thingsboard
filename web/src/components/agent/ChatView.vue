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
            ? 'bg-indigo-100 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-400'
            : 'bg-transparent text-gray-400 hover:text-gray-600 dark:hover:text-gray-300'"
          @click="activePanel = activePanel === 'files' ? null : 'files'"
        >📁 文件</button>
        <!-- Todos toggle -->
        <button
          class="flex items-center gap-1 px-2 py-1 text-[11px] rounded border-none cursor-pointer transition-colors"
          :class="activePanel === 'todos'
            ? 'bg-indigo-100 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-400'
            : 'bg-transparent text-gray-400 hover:text-gray-600 dark:hover:text-gray-300'"
          @click="activePanel = activePanel === 'todos' ? null : 'todos'"
        >
          ✅ 待办
          <span
            v-if="allTodos.length > 0"
            class="text-[10px] px-1 rounded-full"
            :class="activePanel === 'todos'
              ? 'bg-indigo-200 dark:bg-indigo-800'
              : 'bg-gray-100 dark:bg-gray-800'"
          >{{ doneTodoCount }}/{{ allTodos.length }}</span>
        </button>
        <!-- Debug toggle -->
        <button
          class="flex items-center gap-1 px-2 py-1 text-[11px] rounded border-none cursor-pointer transition-colors"
          :class="showDebug
            ? 'bg-indigo-100 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-400'
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
          <!-- Welcome -->
          <div
            v-if="!msgs.length && !loading"
            class="p-5 text-gray-500 dark:text-gray-400"
          >
            <div v-html="welcomeHtml" />
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
            <span class="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style="animation-delay: 0ms" />
            <span class="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style="animation-delay: 150ms" />
            <span class="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style="animation-delay: 300ms" />
          </div>

          <!-- Suggestions -->
          <div v-if="suggestions.length && !loading" class="flex flex-wrap gap-2">
            <button
              v-for="(q, i) in suggestions"
              :key="i"
              class="px-3 py-1.5 text-xs rounded-full border border-gray-200 dark:border-gray-700 bg-transparent text-gray-500 dark:text-gray-400 hover:border-indigo-300 hover:text-indigo-500 cursor-pointer transition-colors"
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
          class="px-4 py-1.5 text-xs text-indigo-500 border-t border-indigo-100 dark:border-indigo-900 bg-indigo-50 dark:bg-indigo-950"
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
import { marked } from 'marked'
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
// Welcome message
// ---------------------------------------------------------------------------
const welcomeMd = `## 🤖 工艺参数分析助手

输入 \`?\` 查看帮助。支持 **8 种** 制造工艺的智能化分析。

| 功能 | 示例 |
|------|------|
| 📊 数据画像 | 「分析D1设备的数据画像」 |
| 🔗 相关性分析 | 「分析温度与剪切强度的相关性」 |
| 📈 回归建模 | 「建立固化温度、时间对强度的回归」 |
| ⭐ 特征重要性 | 「哪些参数对气泡率影响最大」 |
| 📉 SPC 监控 | 「查看 wave-solder-004 的 SPC」 |
| 🧪 DOE 实验 | 「为固化工艺设计 Box-Behnken 实验」 |
| 🎯 参数推荐 | 「推荐提高剪切强度的参数」 |
| 🏭 系统查询 | 「系统有哪些产线」 |
| 🔍 产品追溯 | 「追溯条码 B001」 |
| 🔄 工艺调优 | 输入「优化剪切强度」启动 |

点击下方 ⭐ **工艺调优** 开始引导式参数优化。`

const welcomeHtml = computed(() => marked.parse(welcomeMd, { breaks: true, gfm: true }) as string)

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

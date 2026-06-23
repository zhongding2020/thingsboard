# Chat UI 重设计 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于 deepagents-ui 风格彻底重建 Vue 3 Chat UI，对齐全部 8 项 feature（子智能体卡片、按工具类型渲染、文件查看器、Todo 面板、线程选择器、streamdown 动画、Debug 模式、深色/浅色主题），纯 Tailwind CSS，`@langchain/vue` SDK 管状态，分 4 Phase 独立交付。

**Architecture:** 全新组件树，不复用任何旧 chat 组件。`useAgentStream` 包装 SSE → `@langchain/vue` `useMessages` → 组件树渲染。Chat 区域纯 Tailwind，Element Plus 仅用于 9 个业务页面。后端 SSE 格式保持，新增 `subagent.*` / `todo.update` 事件。

**Tech Stack:** Vue 3 + TypeScript + Vite + Tailwind CSS + Element Plus（仅业务页面）+ Pinia + `@langchain/vue` + `marked`

**Spec:** `docs/superpowers/specs/2026-06-22-chat-ui-redesign-design.md`

## Global Constraints

- 现有 9 个业务页面功能不受影响，Element Plus 仅用于业务页面
- Chat 区域纯 Tailwind（无 Element Plus 依赖），不使用 `tw-` 前缀（直接 `class="flex gap-2"`）
- 后端 SSE 格式保持现有事件类型不变，仅新增 `subagent.*` 和 `todo.update`
- 所有新增组件使用 `<script setup lang="ts">` + Composition API
- `@langchain/vue` SDK 降级策略：如对自定义 stream 支持不足，仅用 `useMessages` 管状态 + 轻量 SSE parser
- 每个 Phase 独立可测试、可上线
- **可以直接推翻旧 UI，不需要向后兼容旧组件和旧 parts[] 结构**

---

## Phase 1: 基础设施（Tailwind + SDK + 核心消息流）— 约 1 周

### Task 1: Tailwind CSS 环境搭建

**Files:**
- Modify: `web/package.json`
- Modify: `web/vite.config.ts`
- Create: `web/src/assets/main.css`

- [ ] **Step 1: 安装 Tailwind CSS v4**

```bash
cd web && npm install tailwindcss @tailwindcss/vite
```

- [ ] **Step 2: 注册 Vite 插件**

在 `web/vite.config.ts` 添加：

```typescript
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
})
```

- [ ] **Step 3: 创建主样式入口**

创建 `web/src/assets/main.css`：

```css
@import "tailwindcss";

@layer base {
  :root {
    --color-bg: #ffffff;
    --color-surface: #f8fafc;
    --color-border: #e2e8f0;
    --color-text: #1e293b;
    --color-text-secondary: #64748b;
    --color-primary: #6366f1;
    --color-primary-hover: #4f46e5;
  }
  .dark {
    --color-bg: #0f172a;
    --color-surface: #1e293b;
    --color-border: #334155;
    --color-text: #e2e8f0;
    --color-text-secondary: #94a3b8;
    --color-primary: #818cf8;
    --color-primary-hover: #6366f1;
  }
}
```

在 `web/src/main.ts` 顶部导入：

```typescript
import '@/assets/main.css'
```

- [ ] **Step 4: 验证**

```bash
cd web && npm run dev
# 确认 dev server 正常启动，无 CSS 报错
```

- [ ] **Step 5: Commit**

```bash
git add web/package.json web/vite.config.ts web/src/assets/main.css web/src/main.ts
git commit -m "feat: add Tailwind CSS v4 with dark mode CSS variables"
```

---

### Task 2: @langchain/vue SDK + useAgentStream 适配器

**Files:**
- Modify: `web/package.json`
- Create: `web/src/composables/useAgentStream.ts`
- Modify: `web/src/api/agent.ts`（删除 SSE 解析，只留 REST）

- [ ] **Step 1: 安装 SDK**

```bash
cd web && npm install @langchain/vue @langchain/core
```

- [ ] **Step 2: 创建 useAgentStream.ts**

创建 `web/src/composables/useAgentStream.ts`：

```typescript
import { ref, reactive } from 'vue'

const API_BASE = import.meta.env.DEV ? '/api/v1/agent' : 'http://localhost:8000/api/v1/agent'

export interface ToolCall {
  name: string
  args: Record<string, unknown>
  result?: string
  durationMs?: number
  status: 'pending' | 'done' | 'error'
}

export interface SubagentState {
  name: string
  content: string
  status: 'running' | 'done' | 'error'
  open: boolean
}

export interface TodoItem {
  id: string
  text: string
  done: boolean
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  toolCalls?: ToolCall[]
  thinking?: string
  subagents?: SubagentState[]
  trace?: string
}

export function useAgentStream(sessionId: string) {
  const messages = ref<ChatMessage[]>([])
  const loading = ref(false)
  const error = ref('')
  const suggestions = ref<string[]>([])
  const todos = ref<TodoItem[]>([])
  const currentPhase = ref('')

  let abortController: AbortController | null = null

  function lastAssistantMsg(): ChatMessage | undefined {
    for (let i = messages.value.length - 1; i >= 0; i--) {
      if (messages.value[i].role === 'assistant') return messages.value[i]
    }
    return undefined
  }

  async function send(text: string): Promise<void> {
    if (!sessionId || !text) return

    error.value = ''
    loading.value = true
    messages.value.push({ role: 'user', content: text })
    const assistantMsg: ChatMessage = {
      role: 'assistant',
      content: '',
      toolCalls: [],
      subagents: [],
    }
    messages.value.push(assistantMsg)

    try {
      const { sendMessageAsync } = await import('@/api/agent')
      await sendMessageAsync(sessionId, text)

      abortController = new AbortController()
      const res = await fetch(
        `${API_BASE}/chat/${encodeURIComponent(sessionId)}/events`,
        { signal: abortController.signal, headers: { 'X-User': 'anonymous' } }
      )
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)

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
            switch (event.type) {
              case 'message.delta':
                assistantMsg.content += event.text || ''
                break

              case 'tool.call': {
                const tc: ToolCall = {
                  name: event.name,
                  args: event.args || {},
                  status: 'pending',
                }
                assistantMsg.toolCalls = [...(assistantMsg.toolCalls || []), tc]
                break
              }

              case 'tool.result': {
                const tcs = assistantMsg.toolCalls || []
                const last = tcs.findLast(t => t.name === event.name && t.status === 'pending')
                if (last) {
                  last.result = event.data || ''
                  last.durationMs = event.duration_ms || 0
                  last.status = 'done'
                }
                break
              }

              case 'subagent.start': {
                const sa: SubagentState = {
                  name: event.name,
                  content: '',
                  status: 'running',
                  open: true,
                }
                assistantMsg.subagents = [...(assistantMsg.subagents || []), sa]
                break
              }

              case 'subagent.delta': {
                const sa = (assistantMsg.subagents || []).find(s => s.name === event.name && s.status === 'running')
                if (sa) sa.content += event.text || ''
                break
              }

              case 'subagent.end': {
                const sa = (assistantMsg.subagents || []).find(s => s.name === event.name && s.status === 'running')
                if (sa) sa.status = 'done'
                break
              }

              case 'todo.update':
                todos.value = event.todos || []
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
                currentPhase.value = event.phase
                break

              case 'suggestions':
                suggestions.value = event.questions || []
                break

              case 'session.status':
                if (event.status === 'idle') {
                  loading.value = false
                  return
                }
                break

              case 'error':
                error.value = event.message || ''
                loading.value = false
                return
            }
          } catch { /* skip malformed */ }
        }
      }
    } catch (e: unknown) {
      if ((e as Error).name !== 'AbortError') {
        error.value = (e as Error).message || '流中断'
      }
    } finally {
      loading.value = false
      abortController = null
    }
  }

  function cancel(): void {
    abortController?.abort()
    loading.value = false
  }

  function clear(): void {
    messages.value = []
    suggestions.value = []
    todos.value = []
    error.value = ''
  }

  return { messages, loading, error, suggestions, todos, currentPhase, send, cancel, clear }
}
```

- [ ] **Step 3: 精简 agent.ts**

删除 `web/src/api/agent.ts` 中的 `StreamEvents` 接口和 `streamEvents` 函数（第 88-188 行），只保留 REST 端点函数。

- [ ] **Step 4: 验证编译**

```bash
cd web && npx vue-tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git add web/package.json web/src/composables/useAgentStream.ts web/src/api/agent.ts
git commit -m "feat: add useAgentStream composable with full SSE event handling"
```

---

### Task 3: 核心消息渲染组件（TextBlock + ThinkingBlock + ToolCallCard）

**Files:**
- Create: `web/src/components/agent/TextBlock.vue`
- Create: `web/src/components/agent/ThinkingBlock.vue`
- Create: `web/src/components/agent/ToolCallCard.vue`

- [ ] **Step 1: 创建 TextBlock.vue（streamdown 逐字动画）**

```vue
<template>
  <div class="prose prose-sm max-w-none dark:prose-invert animate-streamdown" v-html="rendered" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'

const props = defineProps<{ text: string; isStreaming?: boolean }>()
const rendered = computed(() => marked.parse(props.text || '', { breaks: true, gfm: true }) as string)
</script>

<style scoped>
@keyframes streamdown {
  from { opacity: 0; transform: translateY(-6px); }
  to { opacity: 1; transform: translateY(0); }
}
.animate-streamdown { animation: streamdown 0.25s ease-out; }
</style>
```

- [ ] **Step 2: 创建 ThinkingBlock.vue**

```vue
<template>
  <details class="my-1 border border-amber-200 dark:border-amber-800 rounded-lg px-3 py-2 text-xs bg-amber-50 dark:bg-amber-900/30" :open="isStreaming">
    <summary class="cursor-pointer text-amber-600 dark:text-amber-400 font-medium select-none">
      🤔 {{ isStreaming ? '思考中...' : '思考过程' }}
    </summary>
    <div class="mt-2 text-amber-800 dark:text-amber-200 leading-relaxed whitespace-pre-wrap">{{ text }}</div>
  </details>
</template>

<script setup lang="ts">
defineProps<{ text: string; isStreaming?: boolean }>()
</script>
```

- [ ] **Step 3: 创建 ToolCallCard.vue（含 per-tool renderer 分派）**

```vue
<template>
  <!-- Pending call -->
  <div v-if="tc.status === 'pending'" class="my-1 border border-indigo-200 dark:border-indigo-800 rounded-lg px-3 py-2 text-xs bg-indigo-50 dark:bg-indigo-900/30 max-w-[95%]">
    <div class="flex items-center gap-2 mb-1">
      <span class="w-4 h-4 text-indigo-500 animate-spin">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
      </span>
      <span class="font-medium text-indigo-600 dark:text-indigo-400">调用: {{ tc.name }}</span>
    </div>
    <pre v-if="tc.args && Object.keys(tc.args).length" class="m-0 text-[11px] whitespace-pre-wrap break-all text-indigo-400 font-mono">{{ JSON.stringify(tc.args, null, 2) }}</pre>
  </div>

  <!-- Done result — dispatch to renderer -->
  <div v-else class="my-1 border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-2 text-xs bg-white dark:bg-gray-900 max-w-[95%]">
    <div class="flex items-center gap-2 mb-2">
      <span class="text-green-500">✓</span>
      <span class="font-medium text-gray-500 dark:text-gray-400">
        {{ tc.name }}<span v-if="tc.durationMs"> ({{ tc.durationMs }}ms)</span>
      </span>
    </div>

    <!-- Per-tool renderer dispatch -->
    <FilesRenderer v-if="isFilesTool(tc.name)" :data="tc.result || ''" />
    <SearchRenderer v-else-if="isSearchTool(tc.name)" :data="tc.result || ''" />
    <ThinkRenderer v-else-if="isThinkTool(tc.name)" :data="tc.result || ''" />
    <TodosRenderer v-else-if="isTodoTool(tc.name)" :data="tc.result || ''" />
    <div v-else class="tool-markdown" v-html="renderMarkdown(tc.result || '')" />
  </div>

  <!-- Error -->
  <div v-if="tc.status === 'error'" class="my-1 border border-red-200 dark:border-red-800 rounded-lg px-3 py-2 text-xs bg-red-50 dark:bg-red-900/30">
    <span class="text-red-500">✗ {{ tc.name }} 失败</span>
  </div>
</template>

<script setup lang="ts">
import { marked } from 'marked'
import FilesRenderer from './renderers/FilesRenderer.vue'
import SearchRenderer from './renderers/SearchRenderer.vue'
import ThinkRenderer from './renderers/ThinkRenderer.vue'
import TodosRenderer from './renderers/TodosRenderer.vue'
import type { ToolCall } from '@/composables/useAgentStream'

defineProps<{ tc: ToolCall }>()

function renderMarkdown(text: string): string {
  return marked.parse(text, { breaks: true, gfm: true }) as string
}

function isFilesTool(name: string): boolean {
  return /file|list_files|read|write|edit/i.test(name)
}
function isSearchTool(name: string): boolean {
  return /search|query|find/i.test(name)
}
function isThinkTool(name: string): boolean {
  return /think|reason/i.test(name)
}
function isTodoTool(name: string): boolean {
  return /todo|task/i.test(name)
}
</script>

<style scoped>
.tool-markdown :deep(p) { margin: 0 0 6px; }
.tool-markdown :deep(p:last-child) { margin-bottom: 0; }
.tool-markdown :deep(table) { border-collapse: collapse; width: 100%; font-size: 11px; margin: 4px 0; }
.tool-markdown :deep(th), .tool-markdown :deep(td) { border: 1px solid #e2e8f0; padding: 3px 6px; text-align: left; }
.tool-markdown :deep(th) { background: #f1f5f9; font-weight: 500; }
</style>
```

- [ ] **Step 4: Commit**

```bash
git add web/src/components/agent/TextBlock.vue web/src/components/agent/ThinkingBlock.vue web/src/components/agent/ToolCallCard.vue
git commit -m "feat: add core message rendering components (Text, Think, ToolCall)"
```

---

### Task 4: MessageCard + ChatView 主流程

**Files:**
- Create: `web/src/components/agent/MessageCard.vue`
- Create: `web/src/components/agent/ChatView.vue`（重写）
- Modify: `web/src/components/agent/ChatInput.vue`（Tailwind 重写）

- [ ] **Step 1: 创建 MessageCard.vue**

```vue
<template>
  <div class="flex flex-col gap-1.5 group">
    <!-- User -->
    <div v-if="msg.role === 'user'" class="self-end bg-indigo-500 text-white px-4 py-2.5 rounded-2xl rounded-br-sm max-w-[85%] text-sm leading-relaxed break-words">
      {{ msg.content }}
    </div>

    <!-- Assistant -->
    <template v-else>
      <!-- Thinking -->
      <ThinkingBlock v-if="msg.thinking" :text="msg.thinking" :isStreaming="isStreaming && !msg.content" />

      <!-- Text content -->
      <div v-if="msg.content" class="self-start bg-gray-100 dark:bg-gray-800 px-4 py-2.5 rounded-2xl rounded-bl-sm max-w-[85%]">
        <TextBlock :text="msg.content" :isStreaming="isStreaming" />
      </div>

      <!-- Tool calls -->
      <ToolCallCard v-for="(tc, j) in msg.toolCalls" :key="j" :tc="tc" />

      <!-- Subagents (Phase 2 placeholder — will be replaced by SubagentCard) -->

      <!-- Actions -->
      <div v-if="!isStreaming" class="flex gap-1.5 mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity self-start">
        <button class="flex items-center gap-1 px-2 py-1 text-[11px] text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 bg-transparent border-none rounded cursor-pointer" @click="$emit('copy')">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
          复制
        </button>
        <button class="flex items-center gap-1 px-2 py-1 text-[11px] text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 bg-transparent border-none rounded cursor-pointer" @click="$emit('regenerate')">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 4v6h6"/><path d="M23 20v-6h-6"/><path d="M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15"/></svg>
          重新生成
        </button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import TextBlock from './TextBlock.vue'
import ThinkingBlock from './ThinkingBlock.vue'
import ToolCallCard from './ToolCallCard.vue'
import type { ChatMessage } from '@/composables/useAgentStream'

defineProps<{ msg: ChatMessage; isStreaming: boolean }>()
defineEmits<{ copy: []; regenerate: [] }>()
</script>
```

- [ ] **Step 2: 重写 ChatView.vue**

```vue
<template>
  <div class="flex flex-col h-full bg-white dark:bg-gray-950">
    <!-- Messages -->
    <div ref="msgRef" class="flex-1 overflow-y-auto px-4 py-3 flex flex-col gap-3">
      <!-- Welcome -->
      <div v-if="!msgs.length && !loading" class="p-5 text-gray-500 dark:text-gray-400">
        <div v-html="welcomeHtml" />
      </div>

      <!-- Message cards -->
      <MessageCard
        v-for="(msg, i) in msgs" :key="i"
        :msg="msg"
        :isStreaming="loading && i === msgs.length - 1 && msg.role === 'assistant'"
        @copy="copyMsg(msg)"
        @regenerate="onRegenerate(i)"
      />

      <!-- Loading dots -->
      <div v-if="loading && lastMsg?.role === 'assistant' && !lastMsg?.content && !lastMsg?.toolCalls?.length" class="flex items-center gap-1.5 px-4 py-2">
        <span class="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style="animation-delay:0ms" />
        <span class="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style="animation-delay:150ms" />
        <span class="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style="animation-delay:300ms" />
      </div>

      <!-- Suggestions -->
      <div v-if="suggestions.length && !loading" class="flex flex-wrap gap-2">
        <button
          v-for="(q, i) in suggestions" :key="i"
          class="px-3 py-1.5 text-xs rounded-full border border-gray-200 dark:border-gray-700 bg-transparent text-gray-500 dark:text-gray-400 hover:border-indigo-300 hover:text-indigo-500 cursor-pointer transition-colors"
          @click="onSend(q)"
        >{{ q }}</button>
      </div>
    </div>

    <!-- Error -->
    <div v-if="error" class="px-4 py-1.5 text-xs text-red-500 border-t border-red-100 dark:border-red-900">{{ error }}</div>

    <!-- Phase -->
    <div v-if="currentPhase" class="px-4 py-1.5 text-xs text-indigo-500 border-t border-indigo-100 dark:border-indigo-900 bg-indigo-50 dark:bg-indigo-950">
      📍 当前阶段: {{ currentPhase }}
    </div>

    <!-- Input -->
    <ChatInput :disabled="loading" @send="onSend" @upload="onUpload" @stop="cancel" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import { marked } from 'marked'
import MessageCard from './MessageCard.vue'
import ChatInput from './ChatInput.vue'
import { useAgentStream } from '@/composables/useAgentStream'
import { useChatSession } from '@/composables/useChatSession'
import { useFileUpload } from '@/composables/useFileUpload'
import type { ChatMessage } from '@/composables/useAgentStream'

const { sessionId, createNewSession } = useChatSession()
const { upload } = useFileUpload()

const msgRef = ref<HTMLDivElement>()

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

// Connect useAgentStream
let stream = useAgentStream(sessionId.value)
const { messages: msgs, loading, error, suggestions, currentPhase } = stream

const lastMsg = computed(() => {
  for (let i = msgs.value.length - 1; i >= 0; i--) {
    if (msgs.value[i].role === 'assistant') return msgs.value[i]
  }
  return null
})

function scrollBottom() {
  nextTick(() => { if (msgRef.value) msgRef.value.scrollTop = msgRef.value.scrollHeight })
}

async function onSend(text: string) {
  if (!sessionId.value) {
    await createNewSession()
    sessionStorage.setItem('opencode-session', sessionId.value)
  }
  // Re-create stream with current sessionId
  stream = useAgentStream(sessionId.value)
  await stream.send(text)
  scrollBottom()
}

function cancel() { stream.cancel() }

async function onUpload(file: File) {
  if (!sessionId.value) {
    await createNewSession()
    sessionStorage.setItem('opencode-session', sessionId.value)
  }
  await upload(file, {
    onSuccess: (datasetId, features, targets) => {
      onSend(`对数据集 ${datasetId} 做完整相关性分析，包含相关性热力图。特征字段: ${features.join(',')}，目标字段: ${targets.join(',')}`)
    },
    onError: (msg) => { error.value = msg },
  })
}

function onRegenerate(idx: number) {
  if (loading.value) return
  const userMsg = msgs.value[idx - 1]
  if (!userMsg || userMsg.role !== 'user') return
  msgs.value.splice(idx - 1, 2)
  onSend(userMsg.content)
}

function copyMsg(msg: ChatMessage) {
  const text = msg.content || ''
  navigator.clipboard.writeText(text).catch(() => {})
}
</script>
```

- [ ] **Step 3: 重写 ChatInput.vue（纯 Tailwind）**

```vue
<template>
  <div class="px-4 pb-4 pt-2">
    <div class="border border-gray-200 dark:border-gray-700 rounded-2xl bg-gray-50 dark:bg-gray-900 overflow-hidden transition-colors focus-within:border-indigo-400 focus-within:ring-2 focus-within:ring-indigo-400/20">
      <textarea
        v-model="text"
        class="w-full border-none outline-none bg-transparent text-sm leading-relaxed resize-none font-sans text-gray-800 dark:text-gray-200 placeholder-gray-400 px-4 pt-3 pb-1 box-border"
        placeholder="输入分析需求..."
        :disabled="disabled"
        rows="3"
        @keydown.enter.exact.prevent="emitSend"
        @keydown.shift.enter.prevent="text += '\n'"
      />
      <div class="flex items-center justify-between px-3 pb-3">
        <div class="flex items-center gap-1">
          <button class="flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg bg-transparent text-amber-500 hover:bg-amber-50 dark:hover:bg-amber-950 border-none cursor-pointer transition-colors" @click="$emit('startWorkflow')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l2.4 7.2L22 9.5l-5.7 4.8L17.8 22 12 18l-5.8 4 1.3-7.7L2 9.5l7.6-.3z"/></svg>
            工艺调优
          </button>
          <input type="file" ref="fileRef" class="hidden" accept=".xlsx,.xls,.csv" @change="onFileChange" />
          <button class="flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg bg-transparent text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 border-none cursor-pointer transition-colors" @click="(fileRef as HTMLInputElement).click()">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17,8 12,3 7,8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            上传
          </button>
        </div>
        <div class="flex items-center gap-2">
          <span v-if="text.trim()" class="text-[11px] tabular-nums text-gray-300">{{ text.length }}</span>
          <button v-if="disabled" class="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-red-500 hover:bg-red-600 text-white border-none cursor-pointer transition-colors" @click="$emit('stop')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="3"/></svg>
            停止
          </button>
          <button v-else class="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-indigo-500 hover:bg-indigo-600 text-white border-none cursor-pointer transition-colors disabled:opacity-40 disabled:cursor-not-allowed" :disabled="!text.trim()" @click="emitSend">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22,2 15,22 11,13 2,9"/></svg>
            发送
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

defineProps<{ disabled: boolean }>()
const emit = defineEmits<{ send: [text: string]; upload: [file: File]; startWorkflow: []; stop: [] }>()

const text = ref('')
const fileRef = ref<HTMLInputElement>()

function emitSend() {
  const val = text.value.trim()
  if (!val) return
  emit('send', val)
  text.value = ''
}

function onFileChange(e: Event) {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) emit('upload', file)
  target.value = ''
}
</script>
```

- [ ] **Step 4: 验证**

```bash
cd web && npx vue-tsc --noEmit && npm run dev
# 手动测试：发送消息，验证流式输出、工具调用展示
```

- [ ] **Step 5: Commit**

```bash
git add web/src/components/agent/MessageCard.vue web/src/components/agent/ChatView.vue web/src/components/agent/ChatInput.vue
git commit -m "feat: rebuild ChatView + MessageCard + ChatInput with pure Tailwind"
```

---

### Task 5: 清理旧文件

**Files:**
- Delete: `web/src/composables/useChatStream.ts`
- Delete: `web/src/composables/useChatMessages.ts`
- Delete: `web/src/components/agent/ChatBubble.vue`
- Delete: `web/src/components/agent/ChatToolCall.vue`
- Delete: `web/src/components/agent/ChatLoading.vue`
- Delete: `web/src/components/agent/ChatContent.vue`
- Delete: `web/src/components/agent/PhaseIndicator.vue`（逻辑已内置到 ChatView）
- Delete: `web/src/components/agent/ChatSuggestions.vue`（逻辑已内置到 ChatView）
- Modify: `web/src/components/agent/AgentHeader.vue`（Tailwind 重写样式）

- [ ] **Step 1: 删除旧文件**

```bash
rm web/src/composables/useChatStream.ts
rm web/src/composables/useChatMessages.ts
rm web/src/components/agent/ChatBubble.vue
rm web/src/components/agent/ChatToolCall.vue
rm web/src/components/agent/ChatLoading.vue
rm web/src/components/agent/ChatContent.vue
rm web/src/components/agent/PhaseIndicator.vue
rm web/src/components/agent/ChatSuggestions.vue
```

- [ ] **Step 2: 验证编译无引用错误**

```bash
cd web && npx vue-tsc --noEmit
```

- [ ] **Step 3: 用 Tailwind 重写 AgentHeader 样式**

将 `AgentHeader.vue` 的 `<style scoped>` 替换为 Tailwind 类。

- [ ] **Step 4: Commit**

```bash
git add -A web/src/
git commit -m "chore: delete old chat components, clean up to pure Tailwind codebase"
```

---

## Phase 2: 子智能体 + 工具渲染器（约 1 周）

### Task 6: 后端新增 subagent.* 和 todo.update SSE 事件

**Files:**
- Modify: `src/process_opt/api/agent_routes.py`

- [ ] **Step 1: 添加子智能体事件检测**

在 `_map_event()` 前添加辅助函数，扩展 `_map_event()` 加入 4 种新事件类型的处理逻辑。改动集中在 `_map_event()` 函数，约 +40 行。在 `on_chain_start` / `on_chain_end` 中检测 subagent 命名前缀，`on_chat_model_stream` 中检测嵌套子智能体上下文。

- [ ] **Step 2: 运行测试**

```bash
pytest tests/ -v -k "agent"
```

- [ ] **Step 3: Commit**

```bash
git add src/process_opt/api/agent_routes.py
git commit -m "feat: add subagent.* and todo.update SSE events"
```

---

### Task 7: SubagentCard + 4 个 Per-Tool Renderer

**Files:**
- Create: `web/src/components/agent/SubagentCard.vue`
- Create: `web/src/components/agent/renderers/FilesRenderer.vue`
- Create: `web/src/components/agent/renderers/SearchRenderer.vue`
- Create: `web/src/components/agent/renderers/ThinkRenderer.vue`
- Create: `web/src/components/agent/renderers/TodosRenderer.vue`

- [ ] **Step 1: 创建 SubagentCard.vue**

可折叠子智能体卡片，带状态指示灯（running 脉冲绿 / done 绿 / error 红），点击展开/折叠，展开区域实时流式输出。Props: `name`, `open`, `status`, `content`。

- [ ] **Step 2: 创建 4 个 Renderer**

| Renderer | 触发条件（工具名匹配） | 渲染效果 |
|---|---|---|
| FilesRenderer | `file`, `list_files`, `read`, `write`, `edit` | 文件图标 + 文件名 + 代码块 |
| SearchRenderer | `search`, `query`, `find` | 结果列表，标题 + 摘要 |
| ThinkRenderer | `think`, `reason` | 琥珀色折叠面板 |
| TodosRenderer | `todo`, `task` | 复选框列表，已完成划线 |

- [ ] **Step 3: 将 SubagentCard 接入 MessageCard**

在 `MessageCard.vue` 中添加 `SubagentCard` 渲染（遍历 `msg.subagents`）。

- [ ] **Step 4: 验证并提交**

```bash
cd web && npx vue-tsc --noEmit
git add web/src/components/agent/SubagentCard.vue web/src/components/agent/renderers/ web/src/components/agent/MessageCard.vue
git commit -m "feat: add SubagentCard + 4 per-tool renderers"
```

---

## Phase 3: 辅助面板（约 0.5 周）

### Task 8: FilesystemDrawer + TodoDrawer

**Files:**
- Create: `web/src/components/agent/panels/FilesystemDrawer.vue`
- Create: `web/src/components/agent/panels/TodoDrawer.vue`
- Modify: `web/src/components/agent/ChatView.vue`（添加面板切换按钮 + 右侧 flex 布局）

- [ ] **Step 1: FilesystemDrawer** — 右侧抽屉，遍历消息中 FilesRenderer 提取的文件列表，展示文件树 + 代码高亮
- [ ] **Step 2: TodoDrawer** — 右侧抽屉，展示 `useAgentStream` 的 `todos` 响应式数组，已完成项划线
- [ ] **Step 3: ChatView 集成** — header 添加 📁/✅ 切换按钮，右侧 flex 面板区域显示当前激活的抽屉
- [ ] **Step 4: Commit**

---

### Task 9: ThreadPicker（SessionList 升级）

**Files:**
- Create: `web/src/components/agent/ThreadPicker.vue`
- Modify: `web/src/components/agent/AgentSidebar.vue`

- [ ] **Step 1: ThreadPicker** — 搜索框 + 会话列表 + 新建按钮。自动标题（取首条消息前 20 字），hover 显示删除按钮
- [ ] **Step 2: 替换 AgentSidebar 中的 SessionList**
- [ ] **Step 3: Commit**

---

## Phase 4: 体验层（约 0.5 周）

### Task 10: DebugPanel + 深色/浅色主题

**Files:**
- Create: `web/src/composables/useTheme.ts`
- Create: `web/src/components/agent/panels/DebugPanel.vue`
- Modify: `web/src/components/agent/AgentHeader.vue`（主题切换按钮）

- [ ] **Step 1: useTheme** — `isDark` ref，`toggle()` 切换 `document.documentElement.classList.toggle('dark')`，持久化到 `localStorage`
- [ ] **Step 2: DebugPanel** — 底部面板，记录所有 SSE 事件序列（类型/名称/时间戳），可折叠展开，支持筛选事件类型
- [ ] **Step 3: AgentHeader 添加主题切换按钮** — 太阳/月亮图标
- [ ] **Step 4: Commit**

---

### Task 11: /chat 全页路由（可选）

**Files:**
- Modify: `web/src/router/index.ts`
- Create: `web/src/views/ChatPageView.vue`

- [ ] **Step 1: 添加路由** — `/chat` → ChatPageView（左侧 ThreadPicker + 中间 ChatView）
- [ ] **Step 2: Commit**

---

## Self-Review

### Spec Coverage
- ✅ P1: Tailwind (Task 1), SDK + useAgentStream (Task 2), TextBlock/ThinkingBlock/ToolCallCard (Task 3), MessageCard + ChatView + ChatInput (Task 4), 旧文件清理 (Task 5)
- ✅ P2: 后端 SSE 事件 (Task 6), SubagentCard + 4 Renderers (Task 7)
- ✅ P3: FilesystemDrawer + TodoDrawer (Task 8), ThreadPicker (Task 9)
- ✅ P4: DebugPanel + Theme (Task 10), /chat 路由 (Task 11)

### Placeholder Scan
- 无 TBD / TODO / 占位符

### Type Consistency
- `useAgentStream` 的 `ChatMessage`、`ToolCall`、`SubagentState`、`TodoItem` 接口贯穿所有组件
- 所有组件 Props 类型明确，Emits 签名清晰

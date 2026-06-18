# AgentChat.vue 模块化重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 593 行单文件 AgentChat.vue 拆分为 11 个组件 + 5 个 composable，不增依赖，功能 1:1 保持

**Architecture:** 自底向上：先建 composable (逻辑层) 和叶子组件 (渲染层)，再建中层组件 (组合层)，最后改写 AgentChat.vue 为编排层。每步功能可独立验证。

**Tech Stack:** Vue 3 + TypeScript + Element Plus + marked + ECharts + Mermaid

---

### Task 1: 创建目录结构

**Files:**
- Create: `web/src/composables/useDrag.ts`
- Create: `web/src/composables/useChatSession.ts`
- Create: `web/src/composables/useChatMessages.ts`
- Create: `web/src/composables/useChatStream.ts`
- Create: `web/src/composables/useFileUpload.ts`
- Create: `web/src/components/agent/FloatingButton.vue`
- Create: `web/src/components/agent/AgentHeader.vue`
- Create: `web/src/components/agent/SessionList.vue`
- Create: `web/src/components/agent/ChatContent.vue`
- Create: `web/src/components/agent/ChatToolCall.vue`
- Create: `web/src/components/agent/ChatLoading.vue`
- Create: `web/src/components/agent/ChatSuggestions.vue`
- Create: `web/src/components/agent/ChatBubble.vue`
- Create: `web/src/components/agent/ChatInput.vue`
- Create: `web/src/components/agent/ChatView.vue`
- Create: `web/src/components/agent/AgentSidebar.vue`

- [ ] **Step 1: Create directories**

```bash
mkdir -p web/src/composables web/src/components/agent
```

- [ ] **Step 2: Verify directories exist**

```bash
ls -d web/src/composables web/src/components/agent
```

- [ ] **Step 3: Commit**

```bash
git add web/src/composables web/src/components/agent
git commit -m "chore: create composables and agent component directories"
```

---

### Task 2: useDrag composable

**Files:**
- Create: `web/src/composables/useDrag.ts`

- [ ] **Step 1: Write useDrag.ts**

```typescript
import { ref } from 'vue'

export function useDrag() {
  const x = ref(window.innerWidth - 64)
  const y = ref(window.innerHeight / 2 - 22)
  let dragging = false, startX = 0, startY = 0, origX = 0, origY = 0

  function onMouseDown(e: MouseEvent) {
    dragging = true
    startX = e.clientX; startY = e.clientY
    origX = x.value; origY = y.value
    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
  }

  function onMouseMove(e: MouseEvent) {
    if (!dragging) return
    x.value = Math.max(0, Math.min(window.innerWidth - 44, origX + startX - e.clientX))
    y.value = Math.max(0, Math.min(window.innerHeight - 44, origY + e.clientY - startY))
  }

  function onMouseUp() {
    dragging = false
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
  }

  return { x, y, onMouseDown }
}
```

- [ ] **Step 2: Verify file exists and compiles**

```bash
npx vue-tsc --noEmit web/src/composables/useDrag.ts 2>&1 | head -5
```

- [ ] **Step 3: Commit**

```bash
git add web/src/composables/useDrag.ts
git commit -m "feat: add useDrag composable"
```

---

### Task 3: useChatSession composable

**Files:**
- Create: `web/src/composables/useChatSession.ts`

- [ ] **Step 1: Write useChatSession.ts**

```typescript
import { ref } from 'vue'
import { listSessions, createSession, getMessages } from '@/api/agent'

interface SessionItem { id: string; title?: string }

// Module-level singletons — shared across all composable calls
const sessionId = ref('')
const sessions = ref<SessionItem[]>([])
const processTypes = ref<{ process_type: string; display_name: string }[]>([])
const currentProcessType = ref('adhesive_curing')

export function useChatSession() {

  async function refreshSessions() {
    try {
      sessions.value = await listSessions()
      const saved = sessionStorage.getItem('opencode-session')
      if (!sessionId.value) {
        if (saved && sessions.value.some(s => s.id === saved)) sessionId.value = saved
        else if (sessions.value.length) sessionId.value = sessions.value[0].id
      }
    } catch {}
  }

  async function createNewSession(): Promise<string> {
    const res = await createSession(currentProcessType.value)
    sessionId.value = res.id
    sessionStorage.setItem('opencode-session', res.id)
    sessions.value.unshift({ id: res.id, title: res.title || '新会话' })
    return res.id
  }

  async function newSession() {
    sessionStorage.removeItem('opencode-session')
    await createNewSession()
  }

  function switchSession(id: string) {
    sessionId.value = id
    sessionStorage.setItem('opencode-session', id)
  }

  function deleteSession(id: string) {
    sessions.value = sessions.value.filter(s => s.id !== id)
    if (sessionId.value === id) {
      const next = sessions.value[0]
      sessionId.value = next?.id || ''
      if (next) sessionStorage.setItem('opencode-session', next.id)
      else sessionStorage.removeItem('opencode-session')
    }
  }

  async function loadHistory(): Promise<any[]> {
    if (!sessionId.value) return []
    try {
      const msgs = await getMessages(sessionId.value)
      if (!msgs) return []
      return (msgs as any[])
        .filter((m: any) => { const r = m.info?.role || m.role; return r === 'user' || r === 'assistant' })
        .map((m: any) => ({ role: m.info?.role || m.role || 'assistant', text: '', parts: (m.parts || []).map((p: any) => ({ type: p.type || 'text', text: p.text || '' })) }))
    } catch { return [] }
  }

  return { sessionId, sessions, processTypes, currentProcessType, refreshSessions, createNewSession, newSession, switchSession, deleteSession, loadHistory }
}
```

- [ ] **Step 2: Verify compiles**

```bash
npx vue-tsc --noEmit --project web/tsconfig.json 2>&1 | grep useChatSession || echo "OK"
```

- [ ] **Step 3: Commit**

```bash
git add web/src/composables/useChatSession.ts
git commit -m "feat: add useChatSession composable"
```

---

### Task 4: useChatMessages composable

**Files:**
- Create: `web/src/composables/useChatMessages.ts`

- [ ] **Step 1: Write useChatMessages.ts**

```typescript
import { ref } from 'vue'

interface ChatMessage { role: 'user' | 'assistant'; text: string; parts?: any[] }

// Module-level singletons — shared across all composable calls
const messages = ref<ChatMessage[]>([])
const suggestions = ref<string[]>([])

export function useChatMessages() {

  function addUserMessage(text: string) {
    messages.value.push({ role: 'user', text, parts: [{ type: 'text', text }] })
  }

  function addAssistantPlaceholder(): number {
    const idx = messages.value.length
    messages.value.push({ role: 'assistant', text: '', parts: [{ type: 'text', text: '' }] })
    return idx
  }

  function appendDelta(idx: number, delta: string) {
    const parts = messages.value[idx]?.parts
    if (parts && parts.length > 0) {
      const last = parts[parts.length - 1]
      if (last.type === 'text') last.text = (last.text || '') + delta
    }
  }

  function addToolCall(idx: number, name: string, args: any) {
    messages.value[idx]?.parts.push({ type: 'tool_call', text: '', tool: name, args: JSON.stringify(args) })
  }

  function addToolResult(idx: number, name: string, data: string) {
    messages.value[idx]?.parts.push({ type: 'tool_result', text: data.slice(0, 500), tool: name })
  }

  function copyMessage(msg: ChatMessage) {
    const text = msg.parts
      ?.filter(p => p.type === 'text' || p.type === 'step-start' || p.type === 'step-finish')
      .map(p => p.text)
      .join('\n') || msg.text || ''
    navigator.clipboard.writeText(text).catch(() => {})
  }

  function regenerateMessage(idx: number): string | null {
    const userMsg = messages.value[idx - 1]
    if (!userMsg || userMsg.role !== 'user') return null
    const text = userMsg.text || userMsg.parts?.map(p => p.text).join('') || ''
    if (!text) return null
    messages.value.splice(idx - 1, 2)
    return text
  }

  function clear() { messages.value = []; suggestions.value = [] }

  return { messages, suggestions, addUserMessage, addAssistantPlaceholder, appendDelta, addToolCall, addToolResult, copyMessage, regenerateMessage, clear }
}
```

- [ ] **Step 2: Verify compiles**

```bash
npx vue-tsc --noEmit --project web/tsconfig.json 2>&1 | grep useChatMessages || echo "OK"
```

- [ ] **Step 3: Commit**

```bash
git add web/src/composables/useChatMessages.ts
git commit -m "feat: add useChatMessages composable"
```

---

### Task 5: useChatStream composable

**Files:**
- Create: `web/src/composables/useChatStream.ts`

- [ ] **Step 1: Write useChatStream.ts**

```typescript
import { ref } from 'vue'
import { sendMessageAsync, streamEvents, type StreamEvents } from '@/api/agent'

export function useChatStream() {
  const loading = ref(false)
  const error = ref('')
  let activeStream: StreamEvents | null = null

  function cancel() {
    if (activeStream) {
      activeStream.cancel()
      activeStream = null
    }
    loading.value = false
  }

  async function sendAndStream(
    sessionId: string,
    text: string,
    callbacks: {
      onDelta: (delta: string) => void
      onToolCall: (name: string, args: any) => void
      onToolResult: (name: string, data: string) => void
      onDone: () => void
      onError: (msg: string) => void
      onSuggestions: (questions: string[]) => void
    },
  ) {
    error.value = ''
    loading.value = true
    try {
      await sendMessageAsync(sessionId, text)
      activeStream = streamEvents(
        sessionId,
        callbacks.onDelta,
        callbacks.onToolCall,
        callbacks.onToolResult,
        () => {},
        () => { loading.value = false; activeStream = null; callbacks.onDone() },
        (err: string) => { error.value = err; loading.value = false; activeStream = null; callbacks.onError(err) },
        callbacks.onSuggestions,
      )
    } catch (e: any) {
      error.value = '请求失败: ' + (e.message || '')
      loading.value = false
      activeStream = null
    }
  }

  return { loading, error, sendAndStream, cancel }
}
```

- [ ] **Step 2: Verify compiles**

```bash
npx vue-tsc --noEmit --project web/tsconfig.json 2>&1 | grep useChatStream || echo "OK"
```

- [ ] **Step 3: Commit**

```bash
git add web/src/composables/useChatStream.ts
git commit -m "feat: add useChatStream composable"
```

---

### Task 6: useFileUpload composable

**Files:**
- Create: `web/src/composables/useFileUpload.ts`

- [ ] **Step 1: Write useFileUpload.ts**

```typescript
import { ref } from 'vue'
import { useSessionStore } from '@/stores/session'

export function useFileUpload() {
  const uploading = ref(false)

  function getCurrentUser(): string {
    const store = useSessionStore()
    return store.currentUser || 'anonymous'
  }

  async function upload(
    file: File,
    callbacks: {
      onSuccess: (datasetId: string, features: string[], targets: string[]) => void
      onError: (msg: string) => void
    },
  ) {
    if (!file.name.match(/\.(xlsx|xls|csv)$/i)) {
      callbacks.onError('仅支持 .xlsx / .xls / .csv 文件')
      return
    }
    uploading.value = true
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch('/api/v1/agent/upload', {
        method: 'POST',
        headers: { 'X-User': getCurrentUser() },
        body: form,
      })
      if (!res.ok) throw new Error('上传失败')
      const data = await res.json()
      callbacks.onSuccess(data.dataset_id, data.fields?.features || [], data.fields?.targets || [])
    } catch (e: any) {
      callbacks.onError('文件上传失败: ' + (e.message || ''))
    } finally {
      uploading.value = false
    }
  }

  return { uploading, upload }
}
```

- [ ] **Step 2: Verify compiles**

```bash
npx vue-tsc --noEmit --project web/tsconfig.json 2>&1 | grep useFileUpload || echo "OK"
```

- [ ] **Step 3: Commit**

```bash
git add web/src/composables/useFileUpload.ts
git commit -m "feat: add useFileUpload composable"
```

---

### Task 7: ChatContent.vue — 富文本渲染组件

**Files:**
- Create: `web/src/components/agent/ChatContent.vue`

- [ ] **Step 1: Write ChatContent.vue**

```vue
<template>
  <div class="chat-content" v-html="rendered"></div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUpdated, ref } from 'vue'
import { marked } from 'marked'
import mermaid from 'mermaid'
import * as echarts from 'echarts'

mermaid.initialize({ startOnLoad: false, theme: 'default' })

const props = defineProps<{ text: string; uid: string }>()

function findEchartsJson(text: string): string[] {
  const results: string[] = []
  let i = 0
  while (i < text.length) {
    i = text.indexOf('"xAxis"', i)
    if (i === -1) break
    const start = text.lastIndexOf('{', i - 20)
    if (start === -1 || start < i - 100) { i += 6; continue }
    let depth = 0, end = -1
    for (let j = start; j < text.length; j++) {
      if (text[j] === '{') depth++
      else if (text[j] === '}') { depth--; if (depth === 0) { end = j + 1; break } }
    }
    if (end > 0) {
      try {
        const candidate = text.slice(start, end)
        const parsed = JSON.parse(candidate)
        if (parsed.series && (parsed.xAxis || parsed.yAxis)) {
          results.push(candidate)
          i = end
          continue
        }
      } catch {}
    }
    i += 6
  }
  return results
}

const rendered = computed(() => {
  let processed = props.text
  const jsonPatterns = findEchartsJson(props.text)
  for (const json of jsonPatterns) {
    processed = processed.replace(json, '\n```echarts\n' + json + '\n```\n')
  }

  let html = marked.parse(processed, { breaks: true, gfm: true }) as string

  html = html.replace(/<pre><code class="language-echarts">([\s\S]*?)<\/code><\/pre>/g, (_, code) => {
    const id = 'echarts-' + props.uid + '-' + Math.random().toString(36).slice(2, 6)
    setTimeout(() => {
      try {
        const option = JSON.parse(code.trim())
        const el = document.getElementById(id)
        if (!el) return
        const chart = echarts.init(el)
        chart.setOption(option)
        new ResizeObserver(() => chart.resize()).observe(el)
      } catch {}
    }, 50)
    return `<div class="echarts-block" id="${id}" style="width:100%;height:360px"><div class="echarts-loading">渲染图表中...</div></div>`
  })

  html = html.replace(/<pre><code class="language-json">([\s\S]*?)<\/code><\/pre>/g, (_, code) => {
    try {
      const parsed = JSON.parse(code.trim())
      if (parsed.series && (parsed.xAxis || parsed.yAxis)) {
        const id = 'echarts-' + props.uid + '-' + Math.random().toString(36).slice(2, 6)
        setTimeout(() => {
          try {
            const option = JSON.parse(code.trim())
            const el = document.getElementById(id)
            if (!el) return
            const chart = echarts.init(el)
            chart.setOption(option)
            new ResizeObserver(() => chart.resize()).observe(el)
          } catch {}
        }, 50)
        return `<div class="echarts-block" id="${id}" style="width:100%;height:360px"><div class="echarts-loading">渲染图表中...</div></div>`
      }
    } catch {}
    return _
  })

  html = html.replace(/<pre><code class="language-mermaid">([\s\S]*?)<\/code><\/pre>/g, (_, code) => {
    const id = 'mermaid-' + props.uid + '-' + Math.random().toString(36).slice(2, 6)
    setTimeout(() => {
      mermaid.render(id + '-svg', code.trim()).then(({ svg }) => {
        const el = document.getElementById(id)
        if (el) el.innerHTML = svg
      }).catch(() => {
        const el = document.getElementById(id)
        if (el) el.innerHTML = '<pre style="color:red;font-size:12px">图表语法错误</pre>'
      })
    }, 50)
    return `<div class="mermaid-block" id="${id}"><div class="mermaid-loading">渲染图表中...</div></div>`
  })

  return html
})
</script>

<style scoped>
.chat-content :deep(p) { margin: 0 0 8px; }
.chat-content :deep(p:last-child) { margin-bottom: 0; }
.chat-content :deep(code) { background: var(--el-fill-color-dark); padding: 2px 5px; border-radius: 4px; font-size: 12px; }
.chat-content :deep(pre) { background: var(--el-fill-color); padding: 10px; border-radius: 8px; overflow-x: auto; font-size: 12px; }
.chat-content :deep(table) { border-collapse: collapse; width: 100%; font-size: 12px; }
.chat-content :deep(th), .chat-content :deep(td) { border: 1px solid var(--el-border-color-light); padding: 4px 8px; }
.chat-content :deep(th) { background: var(--el-fill-color); }
.chat-content :deep(blockquote) { border-left: 3px solid var(--el-color-primary); padding-left: 10px; color: var(--el-text-color-secondary); }
.mermaid-block { margin: 8px 0; padding: 12px; background: #fff; border-radius: 8px; border: 1px solid var(--el-border-color-light); overflow-x: auto; }
.mermaid-block svg { max-width: 100%; height: auto; }
.mermaid-loading, .echarts-loading { font-size: 12px; color: var(--el-text-color-placeholder); padding: 20px; text-align: center; }
.echarts-block { margin: 8px 0; border-radius: 8px; border: 1px solid var(--el-border-color-light); }
</style>
```

- [ ] **Step 2: Verify compiles**

```bash
npx vue-tsc --noEmit --project web/tsconfig.json 2>&1 | grep ChatContent || echo "OK"
```

- [ ] **Step 3: Commit**

```bash
git add web/src/components/agent/ChatContent.vue
git commit -m "feat: add ChatContent rich content renderer component"
```

---

### Task 8: ChatToolCall.vue — 工具调用/思考过程组件

**Files:**
- Create: `web/src/components/agent/ChatToolCall.vue`

- [ ] **Step 1: Write ChatToolCall.vue**

```vue
<template>
  <details v-if="type === 'reasoning' || type === 'thinking'" class="msg-reasoning" :open="isStreaming">
    <summary>{{ isStreaming ? '思考中...' : '思考过程' }}</summary>
    <div class="reasoning-content" v-html="mdText"></div>
  </details>
  <div v-else-if="type === 'tool_call'" class="msg-tool">
    <div class="tool-label">调用工具: {{ toolName }}</div>
    <pre class="tool-args" v-if="args">{{ args }}</pre>
  </div>
  <div v-else-if="type === 'tool_result'" class="msg-tool">
    <div class="tool-label">工具返回</div>
    <pre class="tool-args">{{ text }}</pre>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'

const props = defineProps<{
  type: string
  text?: string
  toolName?: string
  args?: string
  isStreaming?: boolean
}>()

const mdText = computed(() => marked.parse(props.text || '', { breaks: true, gfm: true }) as string)
</script>

<style scoped>
.msg-reasoning { margin: 2px 0; border: 1px solid var(--el-border-color-light); border-radius: 8px; padding: 6px 10px; font-size: 12px; background: var(--el-color-info-light-9); max-width: 95%; align-self: flex-start; }
.msg-reasoning summary { cursor: pointer; color: var(--el-text-color-secondary); }
.msg-reasoning[open] summary { margin-bottom: 6px; }
.reasoning-content { color: var(--el-text-color-secondary); line-height: 1.5; }
.msg-tool { margin: 2px 0; border: 1px solid var(--el-border-color-light); border-radius: 8px; padding: 6px 10px; font-size: 12px; background: var(--el-fill-color); max-width: 95%; align-self: flex-start; }
.tool-label { color: var(--el-color-primary); margin-bottom: 4px; font-weight: 500; }
.tool-args { margin: 0; font-size: 11px; white-space: pre-wrap; word-break: break-all; color: var(--el-text-color-secondary); }
</style>
```

- [ ] **Step 2: Verify compiles**

```bash
npx vue-tsc --noEmit --project web/tsconfig.json 2>&1 | grep ChatToolCall || echo "OK"
```

- [ ] **Step 3: Commit**

```bash
git add web/src/components/agent/ChatToolCall.vue
git commit -m "feat: add ChatToolCall component"
```

---

### Task 9: ChatLoading.vue + ChatSuggestions.vue — 辅助组件

**Files:**
- Create: `web/src/components/agent/ChatLoading.vue`
- Create: `web/src/components/agent/ChatSuggestions.vue`

- [ ] **Step 1: Write ChatLoading.vue**

```vue
<template>
  <div class="loading-indicator">
    <span class="dot"></span><span class="dot"></span><span class="dot"></span>
  </div>
</template>

<style scoped>
.loading-indicator { display: flex; align-items: center; gap: 6px; padding: 10px 14px; align-self: flex-start; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--el-color-primary); opacity: 0.35; animation: dot-bounce 1.4s ease-in-out infinite both; }
.dot:nth-child(1) { animation-delay: 0s; }
.dot:nth-child(2) { animation-delay: 0.16s; }
.dot:nth-child(3) { animation-delay: 0.32s; }
@keyframes dot-bounce { 0%, 80%, 100% { transform: translateY(0); opacity: 0.35; } 40% { transform: translateY(-6px); opacity: 1; } }
</style>
```

- [ ] **Step 2: Write ChatSuggestions.vue**

```vue
<template>
  <div class="suggestions-bar">
    <div v-for="(q, i) in questions" :key="i" class="suggestion-chip" @click="$emit('select', q)">{{ q }}</div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ questions: string[] }>()
defineEmits<{ select: [q: string] }>()
</script>

<style scoped>
.suggestions-bar { display: flex; flex-wrap: wrap; gap: 8px; padding: 4px 0; align-self: flex-start; }
.suggestion-chip { padding: 6px 12px; border-radius: 14px; font-size: 12px; cursor: pointer; background: linear-gradient(135deg, #667eea22, #764ba222); border: 1px solid var(--el-color-primary-light-7); color: var(--el-color-primary); transition: all 0.2s; white-space: nowrap; max-width: 100%; overflow: hidden; text-overflow: ellipsis; }
.suggestion-chip:hover { background: linear-gradient(135deg, #667eea44, #764ba244); border-color: var(--el-color-primary); transform: translateY(-1px); box-shadow: 0 2px 8px rgba(99,102,241,0.2); }
</style>
```

- [ ] **Step 3: Commit**

```bash
git add web/src/components/agent/ChatLoading.vue web/src/components/agent/ChatSuggestions.vue
git commit -m "feat: add ChatLoading and ChatSuggestions components"
```

---

### Task 10: ChatInput.vue — 输入框 + 文件上传

**Files:**
- Create: `web/src/components/agent/ChatInput.vue`

- [ ] **Step 1: Write ChatInput.vue**

```vue
<template>
  <div class="agent-input">
    <div class="input-wrapper">
      <div class="upload-btn-wrapper">
        <input type="file" ref="fileInputRef" accept=".xlsx,.xls,.csv" @change="onFileChange" style="display:none" />
        <el-button text size="small" @click="(fileInputRef as HTMLInputElement).click()" title="上传数据文件">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17,8 12,3 7,8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
        </el-button>
      </div>
      <textarea v-model="text" class="input-textarea" placeholder="输入分析需求... &#8629; 发送" :disabled="disabled" rows="3" @keydown.enter.exact.prevent="emitSend" />
      <el-button class="input-send" type="primary" size="small" @click="emitSend" :disabled="!text.trim() || disabled" :loading="disabled">
        <svg v-if="!disabled" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22,2 15,22 11,13 2,9"/></svg>
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

defineProps<{ disabled: boolean }>()
const emit = defineEmits<{ send: [text: string]; upload: [file: File] }>()

const text = ref('')
const fileInputRef = ref<HTMLInputElement>()

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

<style scoped>
.agent-input { padding: 10px 14px 14px; border-top: 1px solid var(--el-border-color-light); }
.input-wrapper { display: flex; align-items: flex-end; gap: 8px; background: var(--el-fill-color); border-radius: 14px; padding: 8px 10px; border: 1px solid var(--el-border-color-light); transition: border-color 0.2s; }
.input-wrapper:focus-within { border-color: var(--el-color-primary); }
.input-textarea { flex: 1; border: none; outline: none; background: transparent; font-size: 13px; line-height: 1.5; resize: none; font-family: inherit; color: var(--el-text-color-primary); padding: 2px 4px; }
.input-textarea::placeholder { color: var(--el-text-color-placeholder); }
.input-send { flex-shrink: 0; border-radius: 10px; }
.upload-btn-wrapper { display: flex; align-items: center; padding: 2px; }
</style>
```

- [ ] **Step 2: Verify compiles**

```bash
npx vue-tsc --noEmit --project web/tsconfig.json 2>&1 | grep ChatInput || echo "OK"
```

- [ ] **Step 3: Commit**

```bash
git add web/src/components/agent/ChatInput.vue
git commit -m "feat: add ChatInput component"
```

---

### Task 11: ChatBubble.vue — 单条消息气泡

**Files:**
- Create: `web/src/components/agent/ChatBubble.vue`

- [ ] **Step 1: Write ChatBubble.vue**

```vue
<template>
  <div class="agent-msg">
    <div v-if="msg.role === 'user'" class="msg-bubble user-msg">{{ msg.text }}</div>
    <template v-else>
      <div v-for="(part, j) in msg.parts" :key="j" class="msg-part">
        <ChatToolCall
          v-if="part.type === 'reasoning' || part.type === 'thinking'"
          :type="part.type" :text="part.text" :isStreaming="isStreaming"
        />
        <ChatToolCall
          v-else-if="part.type === 'tool_call'"
          type="tool_call" :toolName="part.tool || part.name" :args="part.args"
        />
        <ChatToolCall
          v-else-if="part.type === 'tool_result'"
          type="tool_result" :text="part.text"
        />
        <div
          v-else-if="part.type === 'text' || !part.type || part.type === 'step-start' || part.type === 'step-finish'"
          class="msg-bubble assistant-msg"
        >
          <ChatContent :text="part.text || ''" :uid="'bubble-' + msgIndex + '-' + j" />
        </div>
      </div>
      <div v-if="!isStreaming" class="msg-actions">
        <el-button text size="small" @click="$emit('copy', msg)">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
          复制
        </el-button>
        <el-button text size="small" @click="$emit('regenerate', msgIndex)">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 4v6h6"/><path d="M23 20v-6h-6"/><path d="M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15"/></svg>
          重新生成
        </el-button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import ChatContent from './ChatContent.vue'
import ChatToolCall from './ChatToolCall.vue'

interface ChatMessage { role: 'user' | 'assistant'; text: string; parts?: any[] }

defineProps<{
  msg: ChatMessage
  msgIndex: number
  isStreaming: boolean
}>()

defineEmits<{
  copy: [msg: ChatMessage]
  regenerate: [idx: number]
}>()
</script>

<style scoped>
.agent-msg { display: contents; }
.agent-msg:hover .msg-actions { opacity: 1; }
.msg-bubble { padding: 10px 14px; border-radius: 10px; font-size: 13px; line-height: 1.6; max-width: 95%; word-break: break-word; }
.user-msg { background: var(--el-color-primary-light-8); align-self: flex-end; }
.assistant-msg { align-self: flex-start; background: var(--el-fill-color); }
.msg-actions { display: flex; gap: 6px; margin-top: 4px; opacity: 0; transition: opacity 0.2s; align-self: flex-start; }
</style>
```

- [ ] **Step 2: Verify compiles**

```bash
npx vue-tsc --noEmit --project web/tsconfig.json 2>&1 | grep ChatBubble || echo "OK"
```

- [ ] **Step 3: Commit**

```bash
git add web/src/components/agent/ChatBubble.vue
git commit -m "feat: add ChatBubble component"
```

---

### Task 12: ChatView.vue — 聊天区域编排者

**Files:**
- Create: `web/src/components/agent/ChatView.vue`

- [ ] **Step 1: Write ChatView.vue**

```vue
<template>
  <div class="agent-messages" ref="msgRef">
    <div v-if="!messages.length && !loading" class="agent-welcome">
      <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" style="color:#6366f1;opacity:0.4;margin-bottom:12px"><path d="M12 2l2.8 6L21 9l-4.5 3.8L17.8 19 12 16l-5.8 3 1.3-6.2L3 9l6.2-1z"/></svg>
      <p>可分析数据、优化参数、监控产线</p>
    </div>
    <ChatBubble
      v-for="(msg, i) in messages" :key="i"
      :msg="msg" :msgIndex="i" :isStreaming="loading && i === messages.length - 1"
      @copy="copyMessage" @regenerate="onRegenerate"
    />
    <ChatLoading v-if="loading" />
    <ChatSuggestions v-if="suggestions.length && !loading" :questions="suggestions" @select="onSuggestion" />
  </div>
  <div v-if="error" class="agent-error">{{ error }}</div>
  <ChatInput :disabled="loading" @send="onSend" @upload="onUpload" />
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import ChatBubble from './ChatBubble.vue'
import ChatLoading from './ChatLoading.vue'
import ChatSuggestions from './ChatSuggestions.vue'
import ChatInput from './ChatInput.vue'
import { useChatMessages } from '@/composables/useChatMessages'
import { useChatStream } from '@/composables/useChatStream'
import { useChatSession } from '@/composables/useChatSession'
import { useFileUpload } from '@/composables/useFileUpload'

const { sessionId, createNewSession } = useChatSession()
const { messages, suggestions, addUserMessage, addAssistantPlaceholder, appendDelta, addToolCall, addToolResult, copyMessage, regenerateMessage, clear } = useChatMessages()
const { loading, error, sendAndStream } = useChatStream()
const { upload } = useFileUpload()

const msgRef = ref<HTMLDivElement>()

function scrollBottom() {
  nextTick(() => { if (msgRef.value) msgRef.value.scrollTop = msgRef.value.scrollHeight })
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

  await sendAndStream(sessionId.value, text, {
    onDelta: (delta: string) => { appendDelta(assistantIdx, delta); scrollBottom() },
    onToolCall: (name: string, args: any) => { addToolCall(assistantIdx, name, args); scrollBottom() },
    onToolResult: (name: string, data: string) => { addToolResult(assistantIdx, name, data); scrollBottom() },
    onDone: () => { scrollBottom() },
    onError: () => { scrollBottom() },
    onSuggestions: (questions: string[]) => { suggestions.value = questions },
  })
}

async function onUpload(file: File) {
  if (!sessionId.value) {
    await createNewSession()
    sessionStorage.setItem('opencode-session', sessionId.value)
  }
  await upload(file, {
    onSuccess: (datasetId: string, features: string[], targets: string[]) => {
      const sid = sessionId.value
      const msg = `对数据集 ${datasetId} 做完整相关性分析，包含相关性热力图。特征字段: ${features.join(',')}，目标字段: ${targets.join(',')}`
      addUserMessage('上传文件: ' + file.name)
      loading && (loading.value = true)
      scrollBottom()
      suggestions.value = []

      const assistantIdx = addAssistantPlaceholder()
      scrollBottom()

      sendAndStream(sid, msg, {
        onDelta: (delta: string) => { appendDelta(assistantIdx, delta); scrollBottom() },
        onToolCall: (name: string, args: any) => { addToolCall(assistantIdx, name, args); scrollBottom() },
        onToolResult: (name: string, data: string) => { addToolResult(assistantIdx, name, data); scrollBottom() },
        onDone: () => { scrollBottom() },
        onError: () => { scrollBottom() },
        onSuggestions: (questions: string[]) => { suggestions.value = questions },
      })
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
</script>

<style scoped>
.agent-messages { flex: 1; overflow-y: auto; padding: 14px; display: flex; flex-direction: column; gap: 10px; }
.agent-error { padding: 6px 14px; font-size: 12px; color: var(--el-color-danger); border-top: 1px solid var(--el-border-color-light); }
.agent-welcome { text-align: center; padding: 60px 24px; color: var(--el-text-color-secondary); }
.agent-welcome p { margin: 4px 0; font-size: 14px; }
</style>
```

- [ ] **Step 2: Verify compiles**

```bash
npx vue-tsc --noEmit --project web/tsconfig.json 2>&1 | grep ChatView || echo "OK"
```

- [ ] **Step 3: Commit**

```bash
git add web/src/components/agent/ChatView.vue
git commit -m "feat: add ChatView component"
```

---

### Task 13: AgentHeader.vue + SessionList.vue

**Files:**
- Create: `web/src/components/agent/AgentHeader.vue`
- Create: `web/src/components/agent/SessionList.vue`

- [ ] **Step 1: Write AgentHeader.vue**

```vue
<template>
  <div class="agent-header">
    <div class="agent-header-left">
      <el-dropdown trigger="click" @command="$emit('switchModel', $event)">
        <el-button text size="small" class="model-btn">
          {{ currentModelLabel }}
          <el-icon><ArrowDown /></el-icon>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item v-for="m in models" :key="m.value" :command="m.value" :class="{ 'is-active': m.value === currentModel }">{{ m.label }}</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <el-dropdown trigger="click" @command="$emit('switchProcess', $event)">
        <el-button text size="small" class="model-btn">
          {{ processTypeLabel }}
          <el-icon><ArrowDown /></el-icon>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item v-for="p in processTypes" :key="p.process_type" :command="p.process_type">{{ p.display_name }}</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
    <div class="agent-header-title">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M12 3l2.5 5.5L20 9.5l-4 4 .5 5.5L12 16l-4.5 3 .5-5.5-4-4L9.5 8.5z"/></svg>
      AI
    </div>
    <div class="agent-header-right">
      <el-button text size="small" @click="$emit('toggleSessions')" :title="showSessions ? '返回' : '历史'">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
      </el-button>
      <el-button text size="small" @click="$emit('newSession')" title="新建">+</el-button>
      <el-button text size="small" @click="$emit('toggleMaximize')" :title="maximized ? '还原' : '最大化'">
        <svg v-if="!maximized" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>
        <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="8" y="8" width="12" height="12" rx="2"/><rect x="4" y="4" width="12" height="12" rx="2"/></svg>
      </el-button>
      <el-button text size="small" @click="$emit('close')" title="关闭">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'

interface Model { label: string; value: string }
interface ProcessType { process_type: string; display_name: string }

const props = defineProps<{
  currentModel: string
  models: Model[]
  processTypes: ProcessType[]
  currentProcessType: string
  showSessions: boolean
  maximized: boolean
}>()

defineEmits<{
  switchModel: [val: string]
  switchProcess: [val: string]
  toggleSessions: []
  newSession: []
  toggleMaximize: []
  close: []
}>()

const currentModelLabel = computed(() => props.models.find(m => m.value === props.currentModel)?.label || '')
const processTypeLabel = computed(() => props.processTypes.find(p => p.process_type === props.currentProcessType)?.display_name || '胶固')
</script>

<style scoped>
.agent-header { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border-bottom: 1px solid var(--el-border-color-light); flex-shrink: 0; gap: 8px; }
.agent-header-title { display: flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 600; color: #6366f1; }
.agent-header-right { display: flex; align-items: center; gap: 2px; }
.model-btn { font-size: 12px; color: var(--el-text-color-secondary); }
</style>
```

- [ ] **Step 2: Write SessionList.vue**

```vue
<template>
  <div class="sessions-view">
    <div class="sessions-title">历史会话 ({{ sessions.length }})</div>
    <div v-for="s in sessions" :key="s.id" class="session-card" :class="{ active: s.id === activeId }" @click="$emit('select', s.id)">
      <div class="session-card-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg></div>
      <div class="session-card-text"><div class="session-card-name">{{ s.title || '会话 ' + s.id.slice(0, 8) }}</div></div>
      <el-button link size="small" class="session-delete" @click.stop="$emit('delete', s.id)">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
      </el-button>
    </div>
    <div v-if="!sessions.length" class="sessions-empty">暂无历史会话</div>
  </div>
</template>

<script setup lang="ts">
interface SessionItem { id: string; title?: string }
defineProps<{ sessions: SessionItem[]; activeId: string }>()
defineEmits<{ select: [id: string]; delete: [id: string] }>()
</script>

<style scoped>
.sessions-view { padding: 4px 0; }
.sessions-title { font-size: 13px; font-weight: 600; padding: 0 0 10px; color: var(--el-text-color-primary); }
.session-card { display: flex; align-items: center; gap: 8px; padding: 8px 10px; border-radius: 8px; cursor: pointer; font-size: 13px; }
.session-card:hover { background: var(--el-fill-color); }
.session-card.active { background: var(--el-color-primary-light-8); color: var(--el-color-primary); }
.session-card-icon { flex-shrink: 0; color: var(--el-text-color-secondary); }
.session-card.active .session-card-icon { color: var(--el-color-primary); }
.session-card-text { flex: 1; overflow: hidden; }
.session-card-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.session-delete { opacity: 0; flex-shrink: 0; }
.session-card:hover .session-delete { opacity: 1; }
.sessions-empty { font-size: 12px; color: var(--el-text-color-secondary); padding: 30px 0; text-align: center; }
</style>
```

- [ ] **Step 3: Commit**

```bash
git add web/src/components/agent/AgentHeader.vue web/src/components/agent/SessionList.vue
git commit -m "feat: add AgentHeader and SessionList components"
```

---

### Task 14: AgentSidebar.vue + FloatingButton.vue

**Files:**
- Create: `web/src/components/agent/AgentSidebar.vue`
- Create: `web/src/components/agent/FloatingButton.vue`

- [ ] **Step 1: Write FloatingButton.vue**

```vue
<template>
  <el-button
    class="agent-float" circle
    :style="{ top: y + 'px', bottom: 'auto', right: 'auto', left: x + 'px' }"
    @click="$emit('click')"
    @mousedown.prevent="onMouseDown"
  >
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l2.5 5.5L20 9.5l-4 4 .5 5.5L12 16l-4.5 3 .5-5.5-4-4L9.5 8.5z"/></svg>
  </el-button>
</template>

<script setup lang="ts">
import { useDrag } from '@/composables/useDrag'
defineEmits<{ click: [] }>()
const { x, y, onMouseDown } = useDrag()
</script>

<style scoped>
.agent-float { position: fixed; z-index: 10000; width: 44px; height: 44px; display: flex; align-items: center; justify-content: center; border-radius: 50%; color: #fff; border: none; cursor: grab; background: linear-gradient(135deg, #6366f1, #8b5cf6); box-shadow: 0 4px 20px rgba(99,102,241,0.4); transition: box-shadow 0.2s; }
.agent-float:active { cursor: grabbing; }
.agent-float:hover { box-shadow: 0 6px 24px rgba(99,102,241,0.55); }
</style>
```

- [ ] **Step 2: Write AgentSidebar.vue**

```vue
<template>
  <Teleport to="body">
    <Transition name="agent-backdrop">
      <div v-if="visible" class="agent-backdrop" @click="$emit('close')" />
    </Transition>
    <Transition name="agent-sidebar">
      <div v-if="visible" class="agent-sidebar" :class="{ maximized }">
        <slot />
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
defineProps<{ visible: boolean; maximized: boolean }>()
defineEmits<{ close: [] }>()
</script>

<style scoped>
.agent-backdrop { position: fixed; inset: 0; z-index: 9999; background: rgba(0,0,0,0.3); }
.agent-backdrop-enter-active, .agent-backdrop-leave-active { transition: opacity 0.25s ease; }
.agent-backdrop-enter-from, .agent-backdrop-leave-to { opacity: 0; }
.agent-sidebar { position: fixed; top: 0; right: 0; z-index: 10001; width: 40vw; max-width: 600px; min-width: 380px; height: 100vh; background: var(--el-bg-color); border-left: 1px solid var(--el-border-color-light); box-shadow: -4px 0 32px rgba(0,0,0,0.15); display: flex; flex-direction: column; transition: width 0.3s ease, max-width 0.3s ease; }
.agent-sidebar.maximized { width: 90vw; max-width: 90vw; }
.agent-sidebar-enter-active, .agent-sidebar-leave-active { transition: transform 0.25s ease; }
.agent-sidebar-enter-from, .agent-sidebar-leave-to { transform: translateX(100%); }
</style>
```

- [ ] **Step 3: Commit**

```bash
git add web/src/components/agent/FloatingButton.vue web/src/components/agent/AgentSidebar.vue
git commit -m "feat: add FloatingButton and AgentSidebar components"
```

---

### Task 15: 改写 AgentChat.vue 为编排层

**Files:**
- Modify: `web/src/components/AgentChat.vue` (完全重写)

- [ ] **Step 1: 备份原始文件，写新 AgentChat.vue**

```vue
<template>
  <div>
    <FloatingButton @click="visible = !visible" />
    <AgentSidebar :visible="visible" :maximized="maximized" @close="visible = false">
      <AgentHeader
        :currentModel="currentModel" :models="models"
        :processTypes="session.processTypes.value" :currentProcessType="session.currentProcessType.value"
        :showSessions="showSessions" :maximized="maximized"
        @switchModel="currentModel = $event"
        @switchProcess="(v: string) => { session.currentProcessType.value = v; onNewSession() }"
        @toggleSessions="showSessions = !showSessions"
        @newSession="onNewSession"
        @toggleMaximize="maximized = !maximized"
        @close="visible = false"
      />
      <div class="agent-messages">
        <SessionList
          v-if="showSessions"
          :sessions="session.sessions.value" :activeId="session.sessionId.value"
          @select="(id: string) => { onSwitchSession(id); showSessions = false }"
          @delete="onDeleteSession"
        />
        <ChatView v-else />
      </div>
    </AgentSidebar>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import FloatingButton from './agent/FloatingButton.vue'
import AgentSidebar from './agent/AgentSidebar.vue'
import AgentHeader from './agent/AgentHeader.vue'
import SessionList from './agent/SessionList.vue'
import ChatView from './agent/ChatView.vue'
import { useChatSession } from '@/composables/useChatSession'
import { useChatMessages } from '@/composables/useChatMessages'

const visible = ref(false)
const maximized = ref(false)
const showSessions = ref(false)
const currentModel = ref('deepseek-v4-flash')

const models = [
  { label: 'DeepSeek V4 Flash', value: 'deepseek-v4-flash' },
  { label: 'DeepSeek V4 Pro', value: 'deepseek-v4-pro' },
  { label: 'DeepSeek V3.2', value: 'deepseek-v3.2' },
  { label: 'Ark Code Latest', value: 'ark-code-latest' },
]

const session = useChatSession()
const messages = useChatMessages()

async function onNewSession() {
  sessionStorage.removeItem('opencode-session')
  await session.newSession()
  messages.clear()
}

function onSwitchSession(id: string) {
  session.switchSession(id)
  messages.clear()
  session.loadHistory().then((ms: any[]) => { messages.messages.value = ms })
}

function onDeleteSession(id: string) {
  session.deleteSession(id)
  if (session.sessionId.value === id) messages.clear()
}
</script>

<style scoped>
.agent-messages { flex: 1; overflow-y: auto; display: flex; flex-direction: column; }
</style>
```

- [ ] **Step 2: Verify frontend builds**

```bash
cd web && npx vite build 2>&1 | tail -5
```

Expect: "✓ built in"

- [ ] **Step 3: Fix any build errors, then commit**

```bash
git add web/src/components/AgentChat.vue
git commit -m "refactor: rewrite AgentChat.vue as component orchestrator"
```

---

### Task 16: 端到端验证

- [ ] **Step 1: 构建 Docker 镜像并启动**

```bash
cd /Users/zhongding/dev/thingsboard && AGENT_API_KEY="${PROCESS_OPT_AGENT_API_KEY}" docker-compose build 2>&1 | tail -3
AGENT_API_KEY="${PROCESS_OPT_AGENT_API_KEY}" docker-compose up -d 2>&1
```

- [ ] **Step 2: 验证健康检查**

```bash
sleep 25 && curl -s http://localhost:8000/health
```

Expect: `{"status":"ok"}`

- [ ] **Step 3: 手动验证以下功能**
  - 打开页面，点击浮动按钮 → 侧边栏弹出
  - 选择模型 → 下拉菜单正常
  - 发送 "你好" → AI 流式回复
  - 回复中应有 Markdown 表格渲染
  - 复制 / 重新生成按钮出现
  - 建议问题 chips 出现
  - 上传 .xlsx 文件 → 自动触发分析
  - 切换/新建/删除会话

- [ ] **Step 4: 最终提交**

```bash
git add -A && git status
git commit -m "refactor: modular AgentChat - 16 files from 1, all features retained"
```

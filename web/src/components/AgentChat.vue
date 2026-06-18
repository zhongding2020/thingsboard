<template>
  <div>
    <el-button
      class="agent-float"
      circle
      :style="{ top: floatY + 'px', bottom: 'auto', right: 'auto', left: floatX + 'px' }"
      @click="visible = !visible"
      @mousedown.prevent="startDrag"
    >
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 3l2.5 5.5L20 9.5l-4 4 .5 5.5L12 16l-4.5 3 .5-5.5-4-4L9.5 8.5z"/>
      </svg>
    </el-button>
    <Teleport to="body">
      <Transition name="agent-backdrop">
        <div v-if="visible" class="agent-backdrop" @click="visible = false" />
      </Transition>
      <Transition name="agent-sidebar">
        <div v-if="visible" class="agent-sidebar" :class="{ maximized }">
          <div class="agent-header">
            <div class="agent-header-left">
              <el-dropdown trigger="click" @command="switchModel">
                <el-button text size="small" class="model-btn">
                  {{ currentModel }}
                  <el-icon><ArrowDown /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item v-for="m in models" :key="m.value" :command="m.value" :class="{ 'is-active': m.value === currentModel }">{{ m.label }}</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
              <el-dropdown trigger="click" @command="(v: string) => { currentProcessType = v; newSession() }">
                <el-button text size="small" class="model-btn">
                  {{ processTypes.find(p => p.process_type === currentProcessType)?.display_name || '胶固' }}
                  <el-icon><ArrowDown /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item v-for="p in processTypes" :key="p.process_type" :command="p.process_type">
                      {{ p.display_name }}
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
            <div class="agent-header-title">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
                <path d="M12 3l2.5 5.5L20 9.5l-4 4 .5 5.5L12 16l-4.5 3 .5-5.5-4-4L9.5 8.5z"/>
              </svg>
              AI
            </div>
            <div class="agent-header-right">
              <el-button text size="small" @click="showSessions = !showSessions" :title="showSessions ? '返回' : '历史'">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
              </el-button>
              <el-button text size="small" @click="newSession" title="新建">+</el-button>
              <el-button text size="small" @click="maximized = !maximized" :title="maximized ? '还原' : '最大化'">
                <svg v-if="!maximized" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>
                <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="8" y="8" width="12" height="12" rx="2"/><rect x="4" y="4" width="12" height="12" rx="2"/></svg>
              </el-button>
              <el-button text size="small" @click="visible = false" title="关闭">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
              </el-button>
            </div>
          </div>
          <div class="agent-messages" ref="msgRef">
            <div v-if="showSessions" class="sessions-view">
              <div class="sessions-title">历史会话 ({{ sessions.length }})</div>
              <div v-for="s in sessions" :key="s.id" class="session-card" :class="{ active: s.id === sessionId }" @click="switchSession(s.id); showSessions = false">
                <div class="session-card-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg></div>
                <div class="session-card-text"><div class="session-card-name">{{ s.title || '会话 ' + s.id.slice(0, 8) }}</div></div>
                <el-button link size="small" class="session-delete" @click.stop="deleteSession(s.id)">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
                </el-button>
              </div>
              <div v-if="!sessions.length" class="sessions-empty">暂无历史会话</div>
            </div>
            <template v-else>
              <div v-if="!messages.length && !loading" class="agent-welcome">
                <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" style="color:#6366f1;opacity:0.4;margin-bottom:12px"><path d="M12 2l2.8 6L21 9l-4.5 3.8L17.8 19 12 16l-5.8 3 1.3-6.2L3 9l6.2-1z"/></svg>
                <p>可分析数据、优化参数、监控产线</p>
              </div>
              <div v-for="(msg, i) in messages" :key="i" class="agent-msg">
                <div v-if="msg.role === 'user'" class="msg-bubble user-msg">{{ msg.text }}</div>
                <template v-else-if="msg.role === 'assistant'">
                  <div v-for="(part, j) in msg.parts" :key="j" class="msg-part">
                    <details v-if="part.type === 'reasoning' || part.type === 'thinking'" class="msg-reasoning" :open="loading && i === messages.length - 1">
                      <summary>{{ loading && i === messages.length - 1 ? '思考中...' : '思考过程' }}</summary>
                      <div class="reasoning-content" v-html="renderMd(part.text)"></div>
                    </details>
                    <div v-else-if="part.type === 'tool_call'" class="msg-tool">
                      <div class="tool-label">调用工具: {{ part.tool || part.name || '' }}</div>
                      <pre class="tool-args" v-if="part.args">{{ part.args }}</pre>
                    </div>
                    <div v-else-if="part.type === 'tool_result'" class="msg-tool">
                      <div class="tool-label">工具返回</div>
                      <pre class="tool-args">{{ part.text }}</pre>
                    </div>
                    <div v-else-if="part.type === 'text' || !part.type || part.type === 'step-start' || part.type === 'step-finish'" class="msg-bubble assistant-msg" v-html="renderContent(part.text)"></div>
                  </div>
                </template>
              </div>
              <div v-if="loading" class="loading-indicator">
                <span class="dot"></span><span class="dot"></span><span class="dot"></span>
              </div>
              <div v-if="suggestions.length && !loading" class="suggestions-bar">
                <div v-for="(q, i) in suggestions" :key="i" class="suggestion-chip" @click="clickSuggestion(q)">{{ q }}</div>
              </div>
            </template>
          </div>
          <div v-if="error" class="agent-error">{{ error }}</div>
          <div v-if="!loading" class="agent-input">
            <div class="input-wrapper">
              <div class="upload-btn-wrapper">
                <input type="file" ref="fileInput" accept=".xlsx,.xls,.csv" @change="handleFileUpload" style="display:none" />
                <el-button text size="small" @click="($refs.fileInput as HTMLInputElement).click()" title="上传数据文件">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17,8 12,3 7,8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                </el-button>
              </div>
              <textarea v-model="input" class="input-textarea" placeholder="输入分析需求... &#8629; 发送" :disabled="loading" rows="3" @keydown.enter.exact.prevent="send" />
              <el-button class="input-send" type="primary" size="small" @click="send" :disabled="!input.trim() || loading" :loading="loading">
                <svg v-if="!loading" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22,2 15,22 11,13 2,9"/></svg>
              </el-button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, onUnmounted } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'
import { listSessions, createSession, sendMessageAsync, streamEvents, getMessages, listProcesses, type StreamEvents } from '@/api/agent'
import { useSessionStore } from '@/stores/session'
import { marked } from 'marked'
import mermaid from 'mermaid'
import * as echarts from 'echarts'

mermaid.initialize({ startOnLoad: false, theme: 'default' })

function renderMd(text: string): string { if (!text) return ''; return marked.parse(text, { breaks: true, gfm: true }) as string }

function renderContent(text: string): string {
  if (!text) return ''

  // Pre-process: detect raw ECharts JSON and wrap in ```echarts
  let processed = text
  const jsonPatterns = findEchartsJson(text)
  for (const json of jsonPatterns) {
    processed = processed.replace(json, '\n```echarts\n' + json + '\n```\n')
  }

  let html = marked.parse(processed, { breaks: true, gfm: true }) as string

  // Handle standard ```echarts blocks
  html = html.replace(/<pre><code class="language-echarts">([\s\S]*?)<\/code><\/pre>/g, (_, code) => {
    const id = 'echarts-' + Math.random().toString(36).slice(2, 10)
    setTimeout(() => renderEcharts(id, code), 50)
    return `<div class="echarts-block" id="${id}" style="width:100%;height:360px"><div class="echarts-loading">渲染图表中...</div></div>`
  })
  // Also handle ```json blocks that contain ECharts-like data
  html = html.replace(/<pre><code class="language-json">([\s\S]*?)<\/code><\/pre>/g, (_, code) => {
    try {
      const parsed = JSON.parse(code.trim())
      if (parsed.series && (parsed.xAxis || parsed.yAxis)) {
        const id = 'echarts-' + Math.random().toString(36).slice(2, 10)
        setTimeout(() => renderEcharts(id, code), 50)
        return `<div class="echarts-block" id="${id}" style="width:100%;height:360px"><div class="echarts-loading">渲染图表中...</div></div>`
      }
    } catch {}
    return _
  })

  html = html.replace(/<pre><code class="language-mermaid">([\s\S]*?)<\/code><\/pre>/g, (_, code) => {
    const id = 'mermaid-' + Math.random().toString(36).slice(2, 10)
    setTimeout(() => renderMermaid(id, code), 50)
    return `<div class="mermaid-block" id="${id}"><div class="mermaid-loading">渲染图表中...</div></div>`
  })
  return html
}

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

async function renderMermaid(id: string, code: string) {
  try {
    const { svg } = await mermaid.render(id + '-svg', code.trim())
    const el = document.getElementById(id)
    if (el) el.innerHTML = svg
  } catch (e: any) {
    const el = document.getElementById(id)
    if (el) el.innerHTML = `<pre style="color:red;font-size:12px">图表语法错误: ${e.message}</pre>`
  }
}

function renderEcharts(id: string, code: string) {
  try {
    const option = JSON.parse(code.trim())
    const el = document.getElementById(id)
    if (!el) return
    const chart = echarts.init(el)
    chart.setOption(option)
    new ResizeObserver(() => chart.resize()).observe(el)
  } catch (e: any) {
    const el = document.getElementById(id)
    if (el) el.innerHTML = `<pre style="color:red;font-size:12px">图表配置错误: ${e.message}</pre>`
  }
}

interface ChatMessage { role: 'user' | 'assistant'; text: string; parts?: any[] }
interface SessionItem { id: string; title?: string }

const visible = ref(false)
const maximized = ref(false)
const showSessions = ref(false)
const input = ref('')
const loading = ref(false)
const error = ref('')
const msgRef = ref<HTMLDivElement>()
const messages = ref<ChatMessage[]>([])
const sessionId = ref('')
const sessions = ref<SessionItem[]>([])
const currentModel = ref('deepseek-v4-flash')
const suggestions = ref<string[]>([])

const processTypes = ref<{process_type: string; display_name: string}[]>([])
const currentProcessType = ref('adhesive_curing')

const models = [
  { label: 'DeepSeek V4 Flash', value: 'deepseek-v4-flash' },
  { label: 'DeepSeek V4 Pro', value: 'deepseek-v4-pro' },
  { label: 'DeepSeek V3.2', value: 'deepseek-v3.2' },
  { label: 'Ark Code Latest', value: 'ark-code-latest' },
]

const floatX = ref(window.innerWidth - 64)
const floatY = ref(window.innerHeight / 2 - 22)
let dragging = false, dragStartX = 0, dragStartY = 0, dragStartFloatX = 0, dragStartFloatY = 0
function startDrag(e: MouseEvent) {
  dragging = true; dragStartX = e.clientX; dragStartY = e.clientY
  dragStartFloatX = floatX.value; dragStartFloatY = floatY.value
  document.addEventListener('mousemove', onDrag); document.addEventListener('mouseup', stopDrag)
}
function onDrag(e: MouseEvent) {
  if (!dragging) return
  floatX.value = Math.max(0, Math.min(window.innerWidth - 44, dragStartFloatX + dragStartX - e.clientX))
  floatY.value = Math.max(0, Math.min(window.innerHeight - 44, dragStartFloatY + e.clientY - dragStartY))
}
function stopDrag() { dragging = false; document.removeEventListener('mousemove', onDrag); document.removeEventListener('mouseup', stopDrag) }

onMounted(async () => { processTypes.value = await listProcesses(); await refreshSessions(); const saved = sessionStorage.getItem('opencode-session'); if (saved && sessions.value.some(s => s.id === saved)) { sessionId.value = saved; await loadHistory() } else if (!sessionId.value && sessions.value.length) { sessionId.value = sessions.value[0].id; await loadHistory() } })

let activeStream: StreamEvents | null = null
onUnmounted(() => { if (activeStream) activeStream.cancel() })

async function refreshSessions() { try { sessions.value = await listSessions(); const saved = sessionStorage.getItem('opencode-session'); if (!sessionId.value) { if (saved && sessions.value.some(s => s.id === saved)) sessionId.value = saved; else if (sessions.value.length) sessionId.value = sessions.value[0].id } } catch (e: any) { error.value = '连接失败: ' + e.message } }
async function createNewSession() { try { const res = await createSession(currentProcessType.value); sessionId.value = res.id; sessionStorage.setItem('opencode-session', res.id); sessions.value.unshift({ id: res.id, title: res.title || '新会话' }); messages.value = []; suggestions.value = [] } catch (e: any) { error.value = '创建失败: ' + e.message } }
async function newSession() { sessionStorage.removeItem('opencode-session'); await createNewSession() }
async function switchSession(id: string) { sessionId.value = id; sessionStorage.setItem('opencode-session', id); messages.value = []; suggestions.value = []; await loadHistory() }
function switchModel(val: string) { currentModel.value = val }
function deleteSession(id: string) { sessions.value = sessions.value.filter(s => s.id !== id); if (sessionId.value === id) { const next = sessions.value[0]; sessionId.value = next?.id || ''; if (next) sessionStorage.setItem('opencode-session', next.id); else sessionStorage.removeItem('opencode-session'); messages.value = []; if (next) loadHistory() } }

async function loadHistory() {
  if (!sessionId.value) return
  try {
    const msgs = await getMessages(sessionId.value)
    if (msgs) {
      messages.value = (msgs as any[]).filter((m: any) => { const r = m.info?.role || m.role; return r === 'user' || r === 'assistant' }).map((m: any) => ({ role: m.info?.role || m.role || 'assistant', text: '', parts: (m.parts || []).map((p: any) => ({ type: p.type || 'text', text: p.text || '' })) }))
      scrollBottom()
    }
  } catch { /* best-effort */ }
}

async function send() {
  const text = input.value.trim(); if (!text || loading.value) return
  input.value = ''; error.value = ''
  messages.value.push({ role: 'user', text, parts: [{ type: 'text', text }] })
  loading.value = true; scrollBottom()
  suggestions.value = []
  try {
    if (!sessionId.value) { await createNewSession(); sessionStorage.setItem('opencode-session', sessionId.value) }

    const assistantIdx = messages.value.length
    messages.value.push({ role: 'assistant', text: '', parts: [{ type: 'text', text: '' }] })
    scrollBottom()

    const sid = sessionId.value
    await sendMessageAsync(sid, text)

    activeStream = streamEvents(
      sid,
      (delta: string) => {
        const parts = messages.value[assistantIdx]?.parts
        if (parts && parts.length > 0) {
          const last = parts[parts.length - 1]
          if (last.type === 'text') {
            last.text = (last.text || '') + delta
          }
        }
        scrollBottom()
      },
      (name: string, args: any) => {
        messages.value[assistantIdx]?.parts.push({
          type: 'tool_call', text: '', tool: name, args: JSON.stringify(args),
        })
        scrollBottom()
      },
      (name: string, data: string) => {
        messages.value[assistantIdx]?.parts.push({
          type: 'tool_result', text: data.slice(0, 500), tool: name,
        })
        scrollBottom()
      },
      (node: string) => {},
      () => {
        loading.value = false
        activeStream = null
        scrollBottom()
      },
      (err: string) => {
        error.value = err
        loading.value = false
        activeStream = null
        scrollBottom()
      },
    )
  } catch (e: any) {
    error.value = '请求失败: ' + (e.message || '')
    loading.value = false
    activeStream = null
    scrollBottom()
  }
}

async function handleFileUpload(e: Event) {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return
  if (!file.name.match(/\.(xlsx|xls|csv)$/i)) {
    error.value = '仅支持 .xlsx / .xls / .csv 文件'
    return
  }
  error.value = ''
  loading.value = true
  try {
    if (!sessionId.value) { await createNewSession(); sessionStorage.setItem('opencode-session', sessionId.value) }
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`/api/v1/agent/upload`, {
      method: 'POST',
      headers: { 'X-User': getCurrentUser() },
      body: form,
    })
    if (!res.ok) throw new Error('上传失败')
    const data = await res.json()

    const sid = sessionId.value
    messages.value.push({ role: 'user', text: `上传文件: ${file.name}`, parts: [{ type: 'text', text: `上传文件: ${file.name}` }] })
    const assistantIdx = messages.value.length
    messages.value.push({ role: 'assistant', text: '', parts: [{ type: 'text', text: '' }] })
    scrollBottom()

    const msg = `对数据集 ${data.dataset_id} 做完整相关性分析，包含相关性热力图。特征字段: ${data.fields.features.join(',')}，目标字段: ${data.fields.targets.join(',')}`
    await sendMessageAsync(sid, msg)

    activeStream = streamEvents(
      sid,
      (delta: string) => {
        const parts = messages.value[assistantIdx]?.parts
        if (parts && parts.length > 0) {
          const last = parts[parts.length - 1]
          if (last.type === 'text') last.text = (last.text || '') + delta
        }
        scrollBottom()
      },
      (name: string, args: any) => {
        messages.value[assistantIdx]?.parts.push({ type: 'tool_call', text: '', tool: name, args: JSON.stringify(args) })
        scrollBottom()
      },
      (name: string, data: string) => {
        messages.value[assistantIdx]?.parts.push({ type: 'tool_result', text: data.slice(0, 500), tool: name })
        scrollBottom()
      },
      (node: string) => {},
      () => { loading.value = false; activeStream = null; scrollBottom() },
      (err: string) => { error.value = err; loading.value = false; activeStream = null; scrollBottom() },
      (questions: string[]) => { suggestions.value = questions },
    )
  } catch (e: any) {
    error.value = '文件上传失败: ' + (e.message || '')
    loading.value = false
  } finally {
    target.value = ''
  }
}

function getCurrentUser(): string {
  const store = useSessionStore()
  return store.currentUser || 'anonymous'
}
function scrollBottom() { nextTick(() => { if (msgRef.value) msgRef.value.scrollTop = msgRef.value.scrollHeight }) }

function clickSuggestion(question: string) {
  input.value = question
  send()
}
</script>

<style scoped>
.agent-float {
  position: fixed; z-index: 10000;
  width: 44px; height: 44px; display: flex; align-items: center; justify-content: center;
  border-radius: 50%; color: #fff; border: none; cursor: grab;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  box-shadow: 0 4px 20px rgba(99,102,241,0.4);
  transition: box-shadow 0.2s;
}
.agent-float:active { cursor: grabbing; }
.agent-float:hover { box-shadow: 0 6px 24px rgba(99,102,241,0.55); }

.agent-backdrop { position: fixed; inset: 0; z-index: 9999; background: rgba(0,0,0,0.3); }
.agent-backdrop-enter-active, .agent-backdrop-leave-active { transition: opacity 0.25s ease; }
.agent-backdrop-enter-from, .agent-backdrop-leave-to { opacity: 0; }

.agent-sidebar {
  position: fixed; top: 0; right: 0; z-index: 10001;
  width: 40vw; max-width: 600px; min-width: 380px; height: 100vh;
  background: var(--el-bg-color);
  border-left: 1px solid var(--el-border-color-light);
  box-shadow: -4px 0 32px rgba(0,0,0,0.15);
  display: flex; flex-direction: column; transition: width 0.3s ease, max-width 0.3s ease;
}
.agent-sidebar.maximized { width: 90vw; max-width: 90vw; }

.agent-sidebar-enter-active, .agent-sidebar-leave-active { transition: transform 0.25s ease; }
.agent-sidebar-enter-from, .agent-sidebar-leave-to { transform: translateX(100%); }

.agent-header { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border-bottom: 1px solid var(--el-border-color-light); flex-shrink: 0; gap: 8px; }
.agent-header-title { display: flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 600; color: #6366f1; }
.agent-header-right { display: flex; align-items: center; gap: 2px; }
.model-btn { font-size: 12px; color: var(--el-text-color-secondary); }

.agent-messages { flex: 1; overflow-y: auto; padding: 14px; display: flex; flex-direction: column; gap: 10px; }

.agent-input { padding: 10px 14px 14px; border-top: 1px solid var(--el-border-color-light); }
.agent-error { padding: 6px 14px; font-size: 12px; color: var(--el-color-danger); border-top: 1px solid var(--el-border-color-light); }

.agent-welcome { text-align: center; padding: 60px 24px; color: var(--el-text-color-secondary); }
.agent-welcome p { margin: 4px 0; font-size: 14px; }

.msg-bubble { padding: 10px 14px; border-radius: 10px; font-size: 13px; line-height: 1.6; max-width: 95%; word-break: break-word; }
.msg-bubble :deep(p) { margin: 0 0 8px; }
.msg-bubble :deep(p:last-child) { margin-bottom: 0; }
.msg-bubble :deep(code) { background: var(--el-fill-color-dark); padding: 2px 5px; border-radius: 4px; font-size: 12px; }
.msg-bubble :deep(pre) { background: var(--el-fill-color); padding: 10px; border-radius: 8px; overflow-x: auto; font-size: 12px; }
.msg-bubble :deep(table) { border-collapse: collapse; width: 100%; font-size: 12px; }
.msg-bubble :deep(th), .msg-bubble :deep(td) { border: 1px solid var(--el-border-color-light); padding: 4px 8px; }
.msg-bubble :deep(th) { background: var(--el-fill-color); }
.msg-bubble :deep(blockquote) { border-left: 3px solid var(--el-color-primary); padding-left: 10px; color: var(--el-text-color-secondary); }
.user-msg { background: var(--el-color-primary-light-8); align-self: flex-end; }
.assistant-msg { align-self: flex-start; background: var(--el-fill-color); }

.msg-reasoning { margin: 2px 0; border: 1px solid var(--el-border-color-light); border-radius: 8px; padding: 6px 10px; font-size: 12px; background: var(--el-color-info-light-9); max-width: 95%; align-self: flex-start; }
.msg-reasoning summary { cursor: pointer; color: var(--el-text-color-secondary); }
.msg-reasoning[open] summary { margin-bottom: 6px; }
.reasoning-content { color: var(--el-text-color-secondary); line-height: 1.5; }

.msg-tool { margin: 2px 0; border: 1px solid var(--el-border-color-light); border-radius: 8px; padding: 6px 10px; font-size: 12px; background: var(--el-fill-color); max-width: 95%; align-self: flex-start; }
.tool-label { color: var(--el-color-primary); margin-bottom: 4px; font-weight: 500; }
.tool-args { margin: 0; font-size: 11px; white-space: pre-wrap; word-break: break-all; color: var(--el-text-color-secondary); }

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

.input-wrapper { display: flex; align-items: flex-end; gap: 8px; background: var(--el-fill-color); border-radius: 14px; padding: 8px 10px; border: 1px solid var(--el-border-color-light); transition: border-color 0.2s; }
.input-wrapper:focus-within { border-color: var(--el-color-primary); }
.input-textarea { flex: 1; border: none; outline: none; background: transparent; font-size: 13px; line-height: 1.5; resize: none; font-family: inherit; color: var(--el-text-color-primary); padding: 2px 4px; }
.input-textarea::placeholder { color: var(--el-text-color-placeholder); }
.input-send { flex-shrink: 0; border-radius: 10px; }

.upload-btn-wrapper { display: flex; align-items: center; padding: 2px; }

.mermaid-block { margin: 8px 0; padding: 12px; background: #fff; border-radius: 8px; border: 1px solid var(--el-border-color-light); overflow-x: auto; }
.mermaid-block svg { max-width: 100%; height: auto; }
.mermaid-loading, .echarts-loading { font-size: 12px; color: var(--el-text-color-placeholder); padding: 20px; text-align: center; }
.echarts-block { margin: 8px 0; border-radius: 8px; border: 1px solid var(--el-border-color-light); }

.loading-indicator {
  display: flex; align-items: center; gap: 6px;
  padding: 10px 14px; align-self: flex-start;
}
.dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--el-color-primary); opacity: 0.35;
  animation: dot-bounce 1.4s ease-in-out infinite both;
}
.dot:nth-child(1) { animation-delay: 0s; }
.dot:nth-child(2) { animation-delay: 0.16s; }
.dot:nth-child(3) { animation-delay: 0.32s; }
@keyframes dot-bounce {
  0%, 80%, 100% { transform: translateY(0); opacity: 0.35; }
  40% { transform: translateY(-6px); opacity: 1; }
}

.suggestions-bar {
  display: flex; flex-wrap: wrap; gap: 8px; padding: 4px 0; align-self: flex-start;
}
.suggestion-chip {
  padding: 6px 12px; border-radius: 14px; font-size: 12px; cursor: pointer;
  background: linear-gradient(135deg, #667eea22, #764ba222);
  border: 1px solid var(--el-color-primary-light-7);
  color: var(--el-color-primary); transition: all 0.2s; white-space: nowrap; max-width: 100%; overflow: hidden; text-overflow: ellipsis;
}
.suggestion-chip:hover {
  background: linear-gradient(135deg, #667eea44, #764ba244);
  border-color: var(--el-color-primary);
  transform: translateY(-1px); box-shadow: 0 2px 8px rgba(99,102,241,0.2);
}
</style>

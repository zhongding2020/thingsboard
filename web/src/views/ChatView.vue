<template>
  <div class="chat-page">
    <div class="chat-header">
      <div class="chat-header-left">
        <el-dropdown trigger="click" @command="switchModel">
          <el-button text size="small" class="model-btn">
            {{ currentModel }}
            <el-icon><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-for="m in models" :key="m.value" :command="m.value" :class="{ 'is-active': m.value === currentModel }">
                {{ m.label }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
      <div class="chat-header-title">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
          <path d="M12 3l2.5 5.5L20 9.5l-4 4 .5 5.5L12 16l-4.5 3 .5-5.5-4-4L9.5 8.5z"/>
        </svg>
        AI 分析助手
      </div>
      <div class="chat-header-right">
        <el-button text size="small" @click="toggleSessions" :title="showSessions ? '返回' : '历史'">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
            <circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>
          </svg>
        </el-button>
        <el-button text size="small" @click="newSession" title="新建">+</el-button>
      </div>
    </div>

    <div class="chat-body" ref="msgRef">
      <div v-if="showSessions" class="sessions-view">
        <div class="sessions-title">历史会话 ({{ sessions.length }})</div>
        <div v-for="s in sessions" :key="s.id" class="session-card" :class="{ active: s.id === sessionId }" @click="switchSession(s.id); showSessions = false">
          <div class="session-card-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>
          </div>
          <div class="session-card-text">
            <div class="session-card-name">{{ s.title || '会话 ' + s.id.slice(0, 8) }}</div>
          </div>
          <el-button link size="small" class="session-delete" @click.stop="deleteSession(s.id)">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
          </el-button>
        </div>
        <div v-if="!sessions.length" class="sessions-empty">暂无历史会话</div>
      </div>

      <template v-else>
        <div v-if="!messages.length && !loading" class="chat-welcome">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" style="color:#6366f1;opacity:0.4;margin-bottom:16px">
            <path d="M12 2l2.8 6L21 9l-4.5 3.8L17.8 19 12 16l-5.8 3 1.3-6.2L3 9l6.2-1z"/>
          </svg>
          <p>我是工厂工艺分析助手</p>
          <p>可分析数据、优化参数、监控产线</p>
        </div>
        <div v-for="(msg, i) in messages" :key="i" class="chat-msg">
          <div v-if="msg.role === 'user'" class="msg-bubble user-msg">{{ msg.text }}</div>
          <template v-else-if="msg.role === 'assistant'">
            <div v-for="(part, j) in msg.parts" :key="j" class="msg-part">
              <details v-if="part.type === 'reasoning'" class="msg-reasoning" :open="loading && i === messages.length - 1">
                <summary>{{ loading && i === messages.length - 1 ? '思考中...' : '已思考' }}</summary>
                <div class="reasoning-content" v-html="renderMd(part.text)"></div>
              </details>
              <div v-else-if="part.type === 'text'" class="msg-bubble assistant-msg" v-html="renderMd(part.text)"></div>
            </div>
          </template>
        </div>
      </template>
    </div>

    <div v-if="error" class="chat-error">{{ error }}</div>
    <div class="chat-input">
      <div class="input-wrapper">
        <textarea
          v-model="input"
          class="input-textarea"
          placeholder="输入分析需求... &#8629; 发送"
          :disabled="loading"
          rows="3"
          @keydown.enter.exact.prevent="send"
        />
        <el-button class="input-send" type="primary" size="small" @click="send" :disabled="!input.trim() || loading" :loading="loading">
          {{ loading ? '分析中' : '发送' }}
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'
import { listSessions, createSession, sendPrompt, getMessages } from '@/api/opencode'
import { marked } from 'marked'

function renderMd(text: string): string {
  if (!text) return ''
  return marked.parse(text, { breaks: true, gfm: true }) as string
}

interface ChatMessage { role: 'user' | 'assistant'; text: string; parts?: any[] }
interface SessionItem { id: string; title?: string }

const input = ref('')
const loading = ref(false)
const error = ref('')
const msgRef = ref<HTMLDivElement>()
const messages = ref<ChatMessage[]>([])
const sessionId = ref('')
const sessions = ref<SessionItem[]>([])
const showSessions = ref(false)
const currentModel = ref('deepseek-v4-flash')

const models = [
  { label: 'DeepSeek V4 Flash', value: 'deepseek-v4-flash' },
  { label: 'DeepSeek V4 Pro', value: 'deepseek-v4-pro' },
  { label: 'DeepSeek V3.2', value: 'deepseek-v3.2' },
  { label: 'Ark Code Latest', value: 'ark-code-latest' },
]

onMounted(async () => { await refreshSessions(); if (sessionId.value) await loadHistory() })

async function refreshSessions() {
  try {
    sessions.value = await listSessions()
    if (!sessionId.value && sessions.value.length) sessionId.value = sessions.value[0].id
  } catch (e: any) { error.value = '连接失败: ' + e.message }
}

async function createNewSession() {
  try {
    const res = await createSession()
    sessionId.value = res.id
    sessions.value.unshift({ id: res.id, title: res.title || '新会话' })
    messages.value = []
  } catch (e: any) { error.value = '创建失败: ' + e.message }
}

async function newSession() { await createNewSession() }

function toggleSessions() { showSessions.value = !showSessions.value }

async function switchSession(id: string) {
  sessionId.value = id; messages.value = []; await loadHistory()
}

function switchModel(val: string) { currentModel.value = val }

function deleteSession(id: string) {
  sessions.value = sessions.value.filter(s => s.id !== id)
  if (sessionId.value === id) { sessionId.value = sessions.value[0]?.id || ''; messages.value = []; loadHistory() }
}

async function loadHistory() {
  if (!sessionId.value) return
  try {
    const msgs = await getMessages(sessionId.value)
    if (msgs) {
      messages.value = (msgs as any[]).filter((m: any) => {
        const r = m.info?.role || m.role; return r === 'user' || r === 'assistant'
      }).map((m: any) => ({ role: m.info?.role || m.role || 'assistant', text: '', parts: (m.parts || []).map((p: any) => ({ type: p.type || 'text', text: p.text || '' })) }))
      scrollBottom()
    }
  } catch { /* best-effort */ }
}

async function send() {
  const text = input.value.trim(); if (!text || loading.value) return
  input.value = ''; error.value = ''
  messages.value.push({ role: 'user', text, parts: [{ type: 'text', text }] })
  loading.value = true; scrollBottom()
  try {
    if (!sessionId.value) await createNewSession()
    const res = await sendPrompt(sessionId.value, text)
    if ((res as any).parts) {
      messages.value.push({ role: 'assistant', text: '', parts: (res as any).parts.map((p: any) => ({ type: p.type || 'text', text: p.text || '' })) })
    }
    scrollBottom()
  } catch (e: any) { error.value = '请求失败: ' + (e.message || '') }
  finally { loading.value = false; scrollBottom() }
}

function scrollBottom() { nextTick(() => { if (msgRef.value) msgRef.value.scrollTop = msgRef.value.scrollHeight }) }
</script>

<style scoped>
.chat-page {
  display: flex; flex-direction: column; height: calc(100vh - 100px);
  margin: -12px;
}
.chat-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 16px; border-bottom: 1px solid var(--el-border-color-light);
  flex-shrink: 0; gap: 8px;
}
.chat-header-title { display: flex; align-items: center; gap: 6px; font-size: 15px; font-weight: 600; color: #6366f1; }
.chat-header-right { display: flex; align-items: center; gap: 4px; }
.model-btn { font-size: 12px; color: var(--el-text-color-secondary); }

.chat-body { flex: 1; overflow-y: auto; padding: 16px 20px; max-width: 900px; margin: 0 auto; width: 100%; }

.chat-welcome { text-align: center; padding: 80px 24px; color: var(--el-text-color-secondary); }
.chat-welcome p { margin: 4px 0; font-size: 15px; }

.chat-msg { margin-bottom: 12px; }
.msg-bubble {
  padding: 10px 14px; border-radius: 10px; font-size: 14px; line-height: 1.6;
  max-width: 85%; word-break: break-word;
}
.msg-bubble :deep(p) { margin: 0 0 8px; }
.msg-bubble :deep(p:last-child) { margin-bottom: 0; }
.msg-bubble :deep(code) { background: var(--el-fill-color-dark); padding: 2px 5px; border-radius: 4px; font-size: 12px; }
.msg-bubble :deep(pre) { background: var(--el-fill-color); padding: 10px; border-radius: 8px; overflow-x: auto; font-size: 12px; }
.msg-bubble :deep(table) { border-collapse: collapse; width: 100%; font-size: 12px; }
.msg-bubble :deep(th), .msg-bubble :deep(td) { border: 1px solid var(--el-border-color-light); padding: 4px 8px; }
.msg-bubble :deep(th) { background: var(--el-fill-color); }
.msg-bubble :deep(blockquote) { border-left: 3px solid var(--el-color-primary); padding-left: 10px; color: var(--el-text-color-secondary); }
.user-msg { background: var(--el-color-primary-light-8); margin-left: auto; }
.assistant-msg { background: var(--el-fill-color); }

.msg-reasoning {
  margin: 4px 0; border: 1px solid var(--el-border-color-light); border-radius: 8px;
  padding: 6px 10px; font-size: 12px; background: var(--el-color-info-light-9);
  max-width: 85%;
}
.msg-reasoning summary { cursor: pointer; color: var(--el-text-color-secondary); }
.msg-reasoning[open] summary { margin-bottom: 6px; }
.reasoning-content { color: var(--el-text-color-secondary); line-height: 1.5; }

.sessions-view { padding: 8px 0; }
.sessions-title { font-size: 14px; font-weight: 600; padding: 0 0 12px; color: var(--el-text-color-primary); }
.session-card {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px; border-radius: 8px; cursor: pointer; font-size: 13px;
}
.session-card:hover { background: var(--el-fill-color); }
.session-card.active { background: var(--el-color-primary-light-8); color: var(--el-color-primary); }
.session-card-icon { flex-shrink: 0; color: var(--el-text-color-secondary); }
.session-card.active .session-card-icon { color: var(--el-color-primary); }
.session-card-text { flex: 1; overflow: hidden; }
.session-card-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.session-delete { opacity: 0; flex-shrink: 0; }
.session-card:hover .session-delete { opacity: 1; }
.sessions-empty { font-size: 13px; color: var(--el-text-color-secondary); padding: 40px 0; text-align: center; }

.chat-input { padding: 10px 20px 16px; border-top: 1px solid var(--el-border-color-light); max-width: 900px; margin: 0 auto; width: 100%; }
.chat-error { padding: 6px 20px; font-size: 12px; color: var(--el-color-danger); text-align: center; }

.input-wrapper {
  display: flex; align-items: flex-end; gap: 8px;
  background: var(--el-fill-color); border-radius: 14px;
  padding: 8px 10px; border: 1px solid var(--el-border-color-light);
  transition: border-color 0.2s;
}
.input-wrapper:focus-within { border-color: var(--el-color-primary); }
.input-textarea { flex: 1; border: none; outline: none; background: transparent; font-size: 14px; line-height: 1.5; resize: none; font-family: inherit; color: var(--el-text-color-primary); padding: 2px 4px; }
.input-send { flex-shrink: 0; border-radius: 10px; }
</style>

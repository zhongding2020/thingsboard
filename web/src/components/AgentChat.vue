<template>
  <div>
    <el-tooltip content="AI 分析助手" placement="left">
      <el-button class="agent-float" circle @click="visible = !visible">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 3l2.5 5.5L20 9.5l-4 4 .5 5.5L12 16l-4.5 3 .5-5.5-4-4L9.5 8.5z"/>
        </svg>
      </el-button>
    </el-tooltip>
    <Teleport to="body">
      <Transition name="agent-sidebar">
        <div v-if="visible" class="agent-sidebar">
          <div class="agent-header">
            <div class="agent-header-title">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
                <path d="M12 3l2.5 5.5L20 9.5l-4 4 .5 5.5L12 16l-4.5 3 .5-5.5-4-4L9.5 8.5z"/>
              </svg>
              AI 分析助手
            </div>
            <div class="agent-header-actions">
              <el-button text size="small" @click="newSession" :disabled="loading">新会话</el-button>
              <el-button text size="small" @click="visible = false">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
              </el-button>
            </div>
          </div>
          <div class="agent-messages" ref="msgRef">
            <div v-if="!messages.length && !loading" class="agent-welcome">
              <div class="welcome-icon">
                <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round">
                  <path d="M12 2l2.8 6L21 9l-4.5 3.8L17.8 19 12 16l-5.8 3 1.3-6.2L3 9l6.2-1z"/>
                  <path d="M15 14.5c1.5 1.2 3 2 4.5 2.5" stroke-width="0.8" opacity="0.5"/>
                  <path d="M12 8v2M10 10h4M12 14v2" stroke-width="0.8" opacity="0.4"/>
                </svg>
              </div>
              <div class="welcome-text">
                <p>我是工厂工艺分析助手</p>
                <p>可分析数据、优化参数、监控产线</p>
              </div>
            </div>
            <div v-for="(msg, i) in messages" :key="i" class="agent-msg">
              <div v-if="msg.role === 'user'" class="msg-bubble user-msg">{{ msg.text }}</div>
              <div v-else-if="msg.role === 'assistant'" class="msg-bubble assistant-msg">{{ msg.text }}</div>
            </div>
          </div>
          <div v-if="error" class="agent-error">{{ error }}</div>
          <div class="agent-input">
            <el-input
              v-model="input"
              placeholder="输入分析需求..."
              @keyup.enter="send"
              :disabled="loading"
            >
              <template #append>
                <el-button @click="send" :disabled="!input.trim() || loading" :loading="loading">
                  {{ loading ? '分析中...' : '发送' }}
                </el-button>
              </template>
            </el-input>
          </div>
        </div>
      </Transition>
      <Transition name="agent-backdrop">
        <div v-if="visible" class="agent-backdrop" @click="visible = false" />
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
import { listSessions, createSession, sendPrompt, getMessages } from '@/api/opencode'

interface ChatMessage {
  role: 'user' | 'assistant'
  text: string
}

const visible = ref(false)
const input = ref('')
const loading = ref(false)
const error = ref('')
const msgRef = ref<HTMLDivElement>()
const messages = ref<ChatMessage[]>([])
const sessionId = ref('')

onMounted(async () => {
  try {
    const sessions = await listSessions()
    if (sessions.length) {
      sessionId.value = sessions[0].id
      await loadHistory()
    } else {
      await createNewSession()
    }
  } catch (e: any) {
    error.value = '连接失败: ' + (e.message || '未知错误')
  }
})

async function createNewSession() {
  const res = await createSession()
  sessionId.value = res.id
}

async function newSession() {
  sessionId.value = ''
  messages.value = []
  await createNewSession()
}

async function loadHistory() {
  if (!sessionId.value) return
  try {
    const msgs = await getMessages(sessionId.value)
    if (msgs) {
      messages.value = msgs
        .filter((m: any) => m.role !== 'system')
        .flatMap((m: any) => {
          const texts: ChatMessage[] = []
          if (m.parts) {
            for (const p of m.parts) {
              if (p.type === 'text' && p.text?.trim()) {
                texts.push({ role: m.role || 'assistant', text: p.text })
              }
            }
          }
          return texts
        })
      scrollBottom()
    }
  } catch {
    // best-effort
  }
}

async function send() {
  const text = input.value.trim()
  if (!text || loading.value) return
  input.value = ''
  error.value = ''

  messages.value.push({ role: 'user', text })
  loading.value = true
  scrollBottom()

  try {
    if (!sessionId.value) {
      await createNewSession()
    }
    const res = await sendPrompt(sessionId.value, text)
    if (res.parts) {
      for (const p of res.parts) {
        if (p.type === 'text' && p.text?.trim()) {
          messages.value.push({ role: 'assistant', text: p.text })
        }
      }
    }
    scrollBottom()
  } catch (e: any) {
    error.value = '请求失败: ' + (e.message || '未知错误')
  } finally {
    loading.value = false
    scrollBottom()
  }
}

function scrollBottom() {
  nextTick(() => {
    if (msgRef.value) msgRef.value.scrollTop = msgRef.value.scrollHeight
  })
}
</script>

<style scoped>
.agent-float {
  position: fixed; right: 18px; bottom: 18px; z-index: 10001;
  width: 44px; height: 44px; display: flex; align-items: center; justify-content: center;
  border-radius: 50%; color: #fff; border: none; cursor: pointer;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  box-shadow: 0 4px 20px rgba(99,102,241,0.4);
  transition: transform 0.2s, box-shadow 0.2s;
}
.agent-float:hover { transform: scale(1.08); box-shadow: 0 6px 24px rgba(99,102,241,0.55); }

.agent-backdrop {
  position: fixed; inset: 0; z-index: 9999;
  background: rgba(0,0,0,0.3);
}
.agent-backdrop-enter-active,
.agent-backdrop-leave-active { transition: opacity 0.25s ease; }
.agent-backdrop-enter-from,
.agent-backdrop-leave-to { opacity: 0; }

.agent-sidebar {
  position: fixed; top: 0; right: 0; z-index: 10000;
  width: 420px; height: 100vh;
  background: var(--el-bg-color);
  border-left: 1px solid var(--el-border-color-light);
  box-shadow: -4px 0 32px rgba(0,0,0,0.15);
  display: flex; flex-direction: column;
}
.agent-sidebar-enter-active,
.agent-sidebar-leave-active { transition: transform 0.25s ease; }
.agent-sidebar-enter-from,
.agent-sidebar-leave-to { transform: translateX(100%); }

.agent-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 16px; border-bottom: 1px solid var(--el-border-color-light);
  flex-shrink: 0;
}
.agent-header-title {
  display: flex; align-items: center; gap: 8px;
  font-size: 15px; font-weight: 600;
  color: #6366f1;
}
.agent-header-actions { display: flex; gap: 2px; align-items: center; }

.agent-messages {
  flex: 1; overflow-y: auto; padding: 14px;
  display: flex; flex-direction: column; gap: 10px;
}

.agent-input {
  padding: 10px 14px; border-top: 1px solid var(--el-border-color-light);
}
.agent-error {
  padding: 6px 14px; font-size: 12px; color: var(--el-color-danger);
  border-top: 1px solid var(--el-border-color-light);
}

.agent-welcome { text-align: center; padding: 60px 24px; color: var(--el-text-color-secondary); }
.welcome-icon { margin-bottom: 16px; color: #6366f1; opacity: 0.4; }
.welcome-text p { margin: 4px 0; font-size: 14px; }

.msg-bubble {
  padding: 10px 14px; border-radius: 10px; font-size: 13px; line-height: 1.6;
  max-width: 90%; white-space: pre-wrap; word-break: break-word;
}
.user-msg { background: var(--el-color-primary-light-8); align-self: flex-end; }
.assistant-msg { align-self: flex-start; background: var(--el-fill-color); }
</style>

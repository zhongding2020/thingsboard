<template>
  <div>
    <el-tooltip content="AI 分析助手" placement="left">
      <el-button class="agent-float" circle @click="visible = !visible">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <path d="M12 6v6l4 2"/>
        </svg>
      </el-button>
    </el-tooltip>
    <Teleport to="body">
      <Transition name="agent-panel">
        <div v-if="visible" class="agent-panel">
          <div class="agent-header">
            <span>AI 分析助手</span>
            <div class="agent-header-actions">
              <el-button text size="small" @click="newSession" :disabled="loading">新会话</el-button>
              <el-button text size="small" @click="visible = false">✕</el-button>
            </div>
          </div>
          <div class="agent-messages" ref="msgRef">
            <div v-if="!messages.length && !loading" class="agent-welcome">
              <div class="welcome-icon">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                  <circle cx="12" cy="12" r="10"/>
                  <path d="M12 6v6l4 2"/>
                </svg>
              </div>
              <div class="welcome-text">
                <p>我是工厂工艺分析助手</p>
                <p>可以帮你做相关性分析、帕累托分析、Cpk 优化、SPC 监控等</p>
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
    if (msgRef.value) {
      msgRef.value.scrollTop = msgRef.value.scrollHeight
    }
  })
}
</script>

<style scoped>
.agent-float {
  position: fixed; right: 16px; bottom: 16px; z-index: 9999;
  width: 40px; height: 40px; display: flex; align-items: center; justify-content: center;
  border-radius: 50%; background: var(--el-color-primary); color: #fff;
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  transition: transform 0.2s, box-shadow 0.2s; border: none; cursor: pointer;
}
.agent-float:hover { transform: scale(1.1); box-shadow: 0 6px 16px rgba(0,0,0,0.4); }

.agent-panel {
  position: fixed; right: 20px; bottom: 72px; z-index: 9998;
  width: 480px; height: 600px;
  background: var(--el-bg-color); border: 1px solid var(--el-border-color-light);
  border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.3);
  display: flex; flex-direction: column; overflow: hidden;
}
.agent-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 14px; border-bottom: 1px solid var(--el-border-color-light);
  font-size: 14px; font-weight: 600; flex-shrink: 0;
}
.agent-header-actions { display: flex; gap: 4px; }
.agent-messages { flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 8px; }
.agent-input { padding: 8px 12px; border-top: 1px solid var(--el-border-color-light); }
.agent-error { padding: 4px 12px; font-size: 12px; color: var(--el-color-danger); border-top: 1px solid var(--el-border-color-light); }

.agent-welcome { text-align: center; padding: 40px 20px; color: var(--el-text-color-secondary); }
.welcome-icon { margin-bottom: 12px; color: var(--el-color-primary); opacity: 0.5; }
.welcome-text p { margin: 4px 0; font-size: 13px; }

.msg-bubble {
  padding: 8px 12px; border-radius: 8px; font-size: 13px; line-height: 1.5;
  max-width: 85%; white-space: pre-wrap;
}
.user-msg { background: var(--el-color-primary-light-8); align-self: flex-end; }
.assistant-msg { align-self: flex-start; }

.agent-panel-enter-active,
.agent-panel-leave-active { transition: opacity 0.2s ease, transform 0.2s ease; }
.agent-panel-enter-from,
.agent-panel-leave-to { opacity: 0; transform: translateY(12px) scale(0.96); pointer-events: none; }
</style>

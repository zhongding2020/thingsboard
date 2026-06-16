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
            <el-button text size="small" @click="visible = false">✕</el-button>
          </div>
          <div class="agent-messages" ref="msgRef">
            <div v-for="(msg, i) in messages" :key="i" class="agent-msg">
              <div v-if="msg.role === 'user'" class="msg-bubble user-msg">{{ msg.content }}</div>
              <div v-else-if="msg.type === 'text'" class="msg-bubble assistant-msg">{{ msg.content }}</div>
              <div v-else-if="msg.type === 'code'" class="msg-code">
                <div class="code-header">
                  <el-icon style="margin-right: 4px;"><Monitor /></el-icon> 生成代码
                  <el-button text size="small" @click="copyCode(msg.content)">复制</el-button>
                </div>
                <pre><code>{{ msg.content }}</code></pre>
              </div>
              <div v-else-if="msg.type === 'result'" class="msg-result">
                <div class="result-header">执行结果 ({{ msg.execution_time || 0 }}s)</div>
                <pre>{{ msg.content }}</pre>
              </div>
              <div v-else-if="msg.type === 'error'" class="msg-error">
                <el-icon><WarningFilled /></el-icon> {{ msg.content }}
              </div>
              <div v-else-if="msg.type === 'status'" class="msg-status">
                <el-icon class="is-loading"><Loading /></el-icon> {{ statusText(msg.content) }}
              </div>
            </div>
            <div v-if="loading" class="msg-loading">
              <span class="thinking-dots"><span>.</span><span>.</span><span>.</span></span>
            </div>
          </div>
          <div class="agent-input">
            <el-input
              v-model="input"
              placeholder="输入分析需求... 如：分析温度对强度的影响"
              @keyup.enter="send"
              :disabled="loading"
            >
              <template #append>
                <el-button @click="send" :disabled="!input.trim() || loading">发送</el-button>
              </template>
            </el-input>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { Monitor, WarningFilled, Loading } from '@element-plus/icons-vue'

const visible = ref(false)
const input = ref('')
const loading = ref(false)
const msgRef = ref<HTMLDivElement>()
const messages = ref<{ role: string; type: string; content: string; execution_time?: number }[]>([])

function statusText(s: string): string {
  if (s === 'thinking') return '分析需求...'
  if (s === 'executing') return '执行代码...'
  return s
}

async function send() {
  const text = input.value.trim()
  if (!text || loading.value) return
  input.value = ''

  messages.value.push({ role: 'user', type: 'text', content: text })
  loading.value = true
  scrollBottom()

  try {
    const response = await fetch('/api/v1/agent/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ message: text }),
    })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)

    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6)
        if (data === '[DONE]') break
        try {
          const parsed = JSON.parse(data)
          messages.value.push({ role: 'assistant', type: parsed.type, content: parsed.content, execution_time: parsed.execution_time })
          scrollBottom()
        } catch {
          // raw text, skip
        }
      }
    }
  } catch (e: any) {
    messages.value.push({ role: 'assistant', type: 'error', content: e.message })
    scrollBottom()
  } finally {
    loading.value = false
    scrollBottom()
  }
}

async function copyCode(code: string) {
  await navigator.clipboard.writeText(code)
}

function scrollBottom() {
  nextTick(() => {
    if (msgRef.value) msgRef.value.scrollTop = msgRef.value.scrollHeight
  })
}
</script>

<style scoped>
.agent-float {
  position: fixed;
  right: 16px;
  bottom: 16px;
  z-index: 9999;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--el-color-primary);
  color: #fff;
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  transition: transform 0.2s, box-shadow 0.2s;
  border: none;
  cursor: pointer;
}
.agent-float:hover {
  transform: scale(1.1);
  box-shadow: 0 6px 16px rgba(0,0,0,0.4);
}

.agent-panel {
  position: fixed;
  right: 20px;
  bottom: 72px;
  z-index: 9998;
  width: 520px;
  height: 640px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.3);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.agent-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  border-bottom: 1px solid var(--el-border-color-light);
  font-size: 14px;
  font-weight: 600;
}

.agent-messages {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.agent-input {
  padding: 8px 12px;
  border-top: 1px solid var(--el-border-color-light);
}

.msg-bubble {
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.5;
  max-width: 85%;
  white-space: pre-wrap;
}
.user-msg { background: var(--el-color-primary-light-8); align-self: flex-end; }
.assistant-msg { align-self: flex-start; }

.msg-code {
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  overflow: hidden;
}
.msg-code .code-header {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color);
  border-bottom: 1px solid var(--el-border-color-light);
}
.msg-code pre {
  margin: 0;
  padding: 10px;
  overflow-x: auto;
  font-size: 11px;
  line-height: 1.4;
  max-height: 300px;
  overflow-y: auto;
}

.msg-result {
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  overflow: hidden;
}
.msg-result .result-header {
  padding: 4px 10px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color);
  border-bottom: 1px solid var(--el-border-color-light);
}
.msg-result pre {
  margin: 0;
  padding: 8px 10px;
  font-size: 11px;
  max-height: 200px;
  overflow-y: auto;
}

.msg-error {
  color: var(--el-color-danger);
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.msg-status {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.msg-loading {
  color: var(--el-text-color-secondary);
  font-size: 14px;
  padding: 4px 0;
}

.thinking-dots span {
  animation: dotPulse 1.4s infinite;
  font-size: 24px;
  line-height: 1;
}
.thinking-dots span:nth-child(2) { animation-delay: 0.2s; }
.thinking-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes dotPulse {
  0%, 80%, 100% { opacity: 0; }
  40% { opacity: 1; }
}

.agent-panel-enter-active,
.agent-panel-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.agent-panel-enter-from,
.agent-panel-leave-to {
  opacity: 0;
  transform: translateY(12px) scale(0.96);
  pointer-events: none;
}
</style>

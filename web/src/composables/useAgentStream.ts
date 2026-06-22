import { ref } from 'vue'

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
                // ES2020 compatible: reverse-copy instead of findLast (ES2023)
                const last = [...tcs].reverse().find(t => t.name === event.name && t.status === 'pending')
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

  return { messages, loading, error, suggestions, todos, currentPhase, lastAssistantMsg, send, cancel, clear }
}

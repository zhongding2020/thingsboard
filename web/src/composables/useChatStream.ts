import { ref } from 'vue'
import { sendMessageAsync } from '@/api/agent'

const API_URL = import.meta.env.DEV ? '/api/v1/agent' : 'http://localhost:8000/api/v1/agent'

interface StreamEvents {
  cancel: () => void
  promise: Promise<void>
}

function getCurrentUser(): string {
  // Minimal inline version; the store import is avoided to keep agent.ts clean.
  return 'anonymous'
}

function streamEvents(
  sessionId: string,
  onDelta: (delta: string) => void,
  onToolCall: (name: string, args: any) => void,
  onToolResult: (name: string, data: string, durationMs: number) => void,
  onNodeStart: (node: string) => void,
  onDone: () => void,
  onError: (err: string) => void,
  onSuggestions?: (questions: string[]) => void,
  onTrace?: (node: string, text: string) => void,
  onPhase?: (phase: string, prevPhase: string, action: string) => void,
  onThinking?: (type: string, text?: string) => void,
): StreamEvents {
  const controller = new AbortController()

  const promise = (async () => {
    try {
      const res = await fetch(`${API_URL}/chat/${encodeURIComponent(sessionId)}/events`, {
        signal: controller.signal,
        headers: { 'X-User': getCurrentUser() },
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      if (!res.body) throw new Error('No response body')

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

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
                onDelta(event.text || '')
                break
              case 'tool.call':
                onToolCall(event.name, event.args)
                break
              case 'tool.result':
                onToolResult(event.name, event.data, event.duration_ms || 0)
                break
              case 'node.start':
                onNodeStart(event.node)
                break
              case 'agent.trace':
                if (onTrace && event.node && event.text) {
                  onTrace(event.node, event.text)
                }
                break
              case 'session.status':
                if (event.status === 'idle') {
                  onDone()
                  return
                }
                break
              case 'thinking.start':
              case 'thinking.delta':
              case 'thinking.done':
                if (onThinking) onThinking(event.type, event.text)
                break
              case 'phase.change':
                if (onPhase) onPhase(event.phase, event.prev_phase || '', event.action || '')
                break
              case 'suggestions':
                if (onSuggestions && event.questions) {
                  onSuggestions(event.questions)
                }
                break
              case 'error':
                onError(event.message || '')
                return
            }
          } catch { /* skip malformed */ }
        }
      }
      onDone()
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        onError(e.message || '流中断')
      }
    }
  })()

  return { cancel: () => controller.abort(), promise }
}

export function useChatStream() {
  const loading = ref(false)
  const error = ref('')
  let activeStream: StreamEvents | null = null
  let cancelled = false

  function cancel() {
    cancelled = true
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
      onToolResult: (name: string, data: string, durationMs: number) => void
      onDone: () => void
      onError: (msg: string) => void
      onSuggestions: (questions: string[]) => void
      onTrace?: (node: string, text: string) => void
      onPhase?: (phase: string, prevPhase: string, action: string) => void
      onThinking?: (type: string, text?: string) => void
    },
  ) {
    error.value = ''
    loading.value = true
    cancelled = false

    const guard = <T extends (...args: any[]) => void>(fn: T): T => {
      return ((...args: any[]) => {
        if (cancelled) return
        fn(...args)
      }) as T
    }

    try {
      await sendMessageAsync(sessionId, text)
      if (cancelled) { loading.value = false; return }

      activeStream = streamEvents(
        sessionId,
        guard(callbacks.onDelta),
        guard(callbacks.onToolCall),
        guard(callbacks.onToolResult),
        () => {},
        () => { loading.value = false; activeStream = null; if (!cancelled) callbacks.onDone() },
        (err: string) => { if (!cancelled) { error.value = err; callbacks.onError(err) } loading.value = false; activeStream = null },
        guard(callbacks.onSuggestions),
        callbacks.onTrace ? guard(callbacks.onTrace) : undefined,
        callbacks.onPhase ? guard(callbacks.onPhase) : undefined,
        callbacks.onThinking ? guard(callbacks.onThinking) : undefined,
      )
    } catch (e: any) {
      if (cancelled) return
      error.value = '请求失败: ' + (e.message || '')
      loading.value = false
      activeStream = null
    }
  }

  return { loading, error, sendAndStream, cancel }
}

import { ref } from 'vue'
import { sendMessageAsync, streamEvents, type StreamEvents } from '@/api/agent'

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

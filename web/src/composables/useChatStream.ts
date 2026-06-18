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
      onToolResult: (name: string, data: string, durationMs: number) => void
      onDone: () => void
      onError: (msg: string) => void
      onSuggestions: (questions: string[]) => void
      onTrace?: (node: string, text: string) => void
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
        callbacks.onTrace,
      )
    } catch (e: any) {
      error.value = '请求失败: ' + (e.message || '')
      loading.value = false
      activeStream = null
    }
  }

  return { loading, error, sendAndStream, cancel }
}

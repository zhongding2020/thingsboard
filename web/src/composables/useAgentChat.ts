/** Minimal chat composable — Vercel AI SDK UI Message Stream Protocol v1.
 *
 * Uses direct fetch + ReadableStream to consume the SSE stream from
 * POST /api/chat. No AI SDK dependency needed at runtime — we just use
 * the protocol format it defines.
 */

import { ref, type Ref } from 'vue'
import { streamToParts, type UIMessage } from './parseUIMessageStream'

const API_URL = import.meta.env.DEV ? '/api/chat' : 'http://localhost:8000/api/chat'

const sessionId = ref(localStorage.getItem('chat_session_id') || '')

function ensureSessionId(): string {
  if (!sessionId.value) {
    sessionId.value = `ses_${Math.random().toString(36).slice(2, 14)}`
    localStorage.setItem('chat_session_id', sessionId.value)
  }
  return sessionId.value
}

export function useAgentChat(processType: string = 'injection_molding') {
  const messages: Ref<UIMessage[]> = ref([])
  const status = ref<'submitted' | 'streaming' | 'ready' | 'error'>('ready')
  const error = ref('')
  const estimatedTokens = ref(0)
  let abort: AbortController | null = null

  async function sendMessage(opts: { text: string }) {
    if (status.value === 'streaming') return

    error.value = ''
    status.value = 'submitted'

    const userMsg: UIMessage = {
      id: `msg_user_${Date.now()}`,
      role: 'user',
      parts: [{ type: 'text', text: opts.text }],
    }
    messages.value.push(userMsg)

    abort = new AbortController()

    try {
      const res = await fetch(API_URL, {
        method: 'POST',
        signal: abort.signal,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: messages.value,
          processType,
          sessionId: ensureSessionId(),
        }),
      })

      if (!res.ok) {
        const bodyText = await res.text()
        let detail = ''
        try { const b = JSON.parse(bodyText); detail = b.detail || b.message || '' } catch { detail = bodyText }
        throw new Error(detail ? `请求失败 (${res.status}): ${detail}` : `请求失败 (${res.status})`)
      }

      status.value = 'streaming'

      const result = await streamToParts(res.body!)
      estimatedTokens.value = result.estimatedTokens
      const assistantMsg: UIMessage = {
        id: `msg_asst_${Date.now()}`,
        role: 'assistant',
        parts: result.parts,
      }
      messages.value.push(assistantMsg)
      status.value = 'ready'
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        error.value = e.message || '请求失败'
      }
      status.value = 'ready'
    }
  }

  function stop() {
    abort?.abort()
    status.value = 'ready'
  }

  return { messages, status, error, estimatedTokens, sendMessage, stop }
}

export function resetSession(): void {
  sessionId.value = ''
  localStorage.removeItem('chat_session_id')
}

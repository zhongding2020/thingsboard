import { useSessionStore } from '@/stores/session'

const API_URL = import.meta.env.DEV ? '/opencode' : 'http://localhost:8000/api/opencode'

function getCurrentUser(): string {
  const store = useSessionStore()
  return store.currentUser || 'anonymous'
}

interface OpencodeSession {
  id: string
  title?: string
}

interface OpencodeMessage {
  id?: string
  info?: { role: string }
  role?: string
  parts: { type: string; text?: string }[]
}

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const controller = new AbortController()
  const isPost = opts?.method === 'POST'
  const timeout = setTimeout(() => controller.abort(), isPost ? 300000 : 15000)
  try {
    const res = await fetch(`${API_URL}${path}`, {
      ...opts,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        'X-User': getCurrentUser(),
        ...opts?.headers,
      },
    })
  if (!res.ok) {
    const body = await res.text()
    let detail = `${res.status} ${res.statusText}`
    try {
      const json = JSON.parse(body)
      detail = json.detail || detail
    } catch {}
    throw new Error(detail)
  }
  return res.json() as Promise<T>
  } finally {
    clearTimeout(timeout)
  }
}

export async function listSessions(): Promise<OpencodeSession[]> {
  return request<OpencodeSession[]>('/session')
}

export async function createSession(): Promise<OpencodeSession> {
  return request<OpencodeSession>('/session', {
    method: 'POST',
    body: JSON.stringify({ title: '工厂分析' }),
  })
}

export async function sendPrompt(sessionId: string, text: string): Promise<OpencodeMessage> {
  return request<OpencodeMessage>(`/session/${encodeURIComponent(sessionId)}/message`, {
    method: 'POST',
    body: JSON.stringify({
      parts: [{ type: 'text', text }],
    }),
  })
}

export async function sendPromptAsync(sessionId: string, text: string): Promise<void> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 30000)
  try {
    const res = await fetch(`${API_URL}/session/${encodeURIComponent(sessionId)}/message`, {
      method: 'POST',
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        'X-User': getCurrentUser(),
      },
      body: JSON.stringify({ parts: [{ type: 'text', text }] }),
    })
    if (!res.ok) {
      const body = await res.text()
      let detail = `${res.status} ${res.statusText}`
      try { detail = JSON.parse(body).detail || detail } catch {}
      throw new Error(detail)
    }
  } finally {
    clearTimeout(timeout)
  }
}

export interface StreamEvents {
  cancel: () => void
  promise: Promise<void>
}

export function streamEvents(
  sessionId: string,
  onDelta: (delta: string) => void,
  onPartMeta: (partType: string) => void,
  onDone: () => void,
  onError: (err: string) => void,
): StreamEvents {
  const controller = new AbortController()
  let assistantMsgId: string | null = null

  const promise = (async () => {
    try {
      const res = await fetch(`${API_URL}/session/${encodeURIComponent(sessionId)}/events`, {
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
            const props = event.properties || {}
            if (props.sessionID !== sessionId) continue

            switch (event.type) {
              case 'message.updated':
                if (props.info?.role === 'assistant') {
                  assistantMsgId = props.info.id
                }
                break

              case 'message.part.updated': {
                const part = props.part
                if (part?.messageID) {
                  if (!assistantMsgId) assistantMsgId = part.messageID
                  if (part.messageID === assistantMsgId) {
                    onPartMeta(part.type)
                  }
                }
                break
              }

              case 'message.part.delta':
                if (props.field === 'text') {
                  if (!assistantMsgId) assistantMsgId = props.messageID
                  if (props.messageID === assistantMsgId) {
                    onDelta(props.delta)
                  }
                }
                break

              case 'session.status':
                if (props.status?.type === 'idle') {
                  onDone()
                  return
                }
                break
            }
          } catch {}
        }
      }
      onDone()
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        onError(e.message || '流中断')
      }
    }
  })()

  return {
    cancel: () => controller.abort(),
    promise,
  }
}

export async function getMessages(sessionId: string): Promise<OpencodeMessage[]> {
  return request<OpencodeMessage[]>(`/session/${encodeURIComponent(sessionId)}/message`)
}

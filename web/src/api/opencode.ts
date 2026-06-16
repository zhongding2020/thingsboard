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
  const res = await fetch(`${API_URL}${path}`, {
    ...opts,
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

export async function getMessages(sessionId: string): Promise<OpencodeMessage[]> {
  return request<OpencodeMessage[]>(`/session/${encodeURIComponent(sessionId)}/message`)
}

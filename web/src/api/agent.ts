import { useSessionStore } from '@/stores/session'

const API_URL = import.meta.env.DEV ? '/api/v1/agent' : 'http://localhost:8000/api/v1/agent'

function getCurrentUser(): string {
  const store = useSessionStore()
  return store.currentUser || 'anonymous'
}

interface AgentSession {
  session_id?: string
  id?: string
  process_type?: string
  title?: string
}

interface ChatMessage {
  role: string
  content: string
}

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 15000)
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
      try { detail = JSON.parse(body).detail || detail } catch {}
      throw new Error(detail)
    }
    return res.json() as Promise<T>
  } finally {
    clearTimeout(timeout)
  }
}

export async function listSessions(): Promise<AgentSession[]> {
  const sessions = await request<any[]>('/session')
  return sessions.map((s: any) => ({
    id: s.session_id || s.id,
    title: s.process_type || s.title || '',
    process_type: s.process_type,
  }))
}

export async function createSession(processType?: string): Promise<AgentSession> {
  const res = await request<any>('/session', {
    method: 'POST',
    body: JSON.stringify({ process_type: processType || 'adhesive_curing' }),
  })
  return { id: res.session_id || res.id, process_type: res.process_type }
}

export async function sendMessageAsync(sessionId: string, text: string): Promise<void> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 30000)
  try {
    const res = await fetch(`${API_URL}/chat`, {
      method: 'POST',
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        'X-User': getCurrentUser(),
      },
      body: JSON.stringify({ session_id: sessionId, text }),
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

export async function getMessages(sessionId: string): Promise<ChatMessage[]> {
  return request<ChatMessage[]>(`/session/${encodeURIComponent(sessionId)}/messages`)
}

export async function listProcesses(): Promise<{process_type: string; display_name: string}[]> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 15000)
  try {
    const res = await fetch(`${API_URL}/processes`, {
      signal: controller.signal,
      headers: { 'X-User': getCurrentUser() },
    })
    if (!res.ok) return [{ process_type: 'adhesive_curing', display_name: '点胶固化' }]
    return res.json()
  } catch {
    return [{ process_type: 'adhesive_curing', display_name: '点胶固化' }]
  } finally {
    clearTimeout(timeout)
  }
}

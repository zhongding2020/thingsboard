import { ref } from 'vue'
import { listSessions, createSession, getMessages } from '@/api/agent'

interface SessionItem { id: string; title?: string }

const sessionId = ref('')
const sessions = ref<SessionItem[]>([])
const processTypes = ref<{ process_type: string; display_name: string }[]>([])
const currentProcessType = ref('adhesive_curing')

export function useChatSession() {
  async function refreshSessions() {
    try {
      sessions.value = (await listSessions()) as any
      const saved = sessionStorage.getItem('opencode-session')
      if (!sessionId.value) {
        if (saved && sessions.value.some(s => s.id === saved)) sessionId.value = saved!
        else if (sessions.value.length) sessionId.value = sessions.value[0].id
      }
    } catch {}
  }

  async function createNewSession(): Promise<string> {
    const res = await createSession(currentProcessType.value)
    sessionId.value = res.id!
    sessionStorage.setItem('opencode-session', res.id!)
    sessions.value.unshift({ id: res.id!, title: res.title || '新会话' })
    return res.id!
  }

  async function newSession() {
    sessionStorage.removeItem('opencode-session')
    await createNewSession()
  }

  function switchSession(id: string) {
    sessionId.value = id
    sessionStorage.setItem('opencode-session', id)
  }

  function deleteSession(id: string) {
    sessions.value = sessions.value.filter(s => s.id !== id)
    if (sessionId.value === id) {
      const next = sessions.value[0]
      sessionId.value = next?.id || ''
      if (next) sessionStorage.setItem('opencode-session', next.id)
      else sessionStorage.removeItem('opencode-session')
    }
  }

  async function loadHistory(): Promise<any[]> {
    if (!sessionId.value) return []
    try {
      const msgs = await getMessages(sessionId.value)
      if (!msgs) return []
      return (msgs as any[])
        .filter((m: any) => { const r = m.info?.role || m.role; return r === 'user' || r === 'assistant' })
        .map((m: any) => ({ role: m.info?.role || m.role || 'assistant', text: '', parts: (m.parts || []).map((p: any) => ({ type: p.type || 'text', text: p.text || '' })) }))
    } catch { return [] }
  }

  return { sessionId, sessions, processTypes, currentProcessType, refreshSessions, createNewSession, newSession, switchSession, deleteSession, loadHistory }
}

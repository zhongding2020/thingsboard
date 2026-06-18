import { ref } from 'vue'

interface ChatMessage { role: 'user' | 'assistant'; text: string; parts?: any[] }

const messages = ref<ChatMessage[]>([])
const suggestions = ref<string[]>([])

export function useChatMessages() {
  function addUserMessage(text: string) {
    messages.value.push({ role: 'user', text, parts: [{ type: 'text', text }] })
  }

  function addAssistantPlaceholder(): number {
    const idx = messages.value.length
    messages.value.push({ role: 'assistant', text: '', parts: [{ type: 'text', text: '' }] })
    return idx
  }

  function appendDelta(idx: number, delta: string) {
    const parts = messages.value[idx]?.parts
    if (parts && parts.length > 0) {
      const last = parts[parts.length - 1]
      if (last.type === 'text') last.text = (last.text || '') + delta
    }
  }

  function addToolCall(idx: number, name: string, args: any) {
    const parts = messages.value[idx]?.parts
    if (parts) parts.push({ type: 'tool_call', text: '', tool: name, args: JSON.stringify(args) })
  }

  function addToolResult(idx: number, name: string, data: string, durationMs: number = 0) {
    const parts = messages.value[idx]?.parts
    if (parts) parts.push({ type: 'tool_result', text: data, tool: name, durationMs })
  }

  function addTrace(idx: number, node: string, text: string) {
    const parts = messages.value[idx]?.parts
    if (parts) parts.push({ type: 'trace', text, node })
  }

  function copyMessage(msg: ChatMessage) {
    const text = msg.parts
      ?.filter(p => p.type === 'text' || p.type === 'step-start' || p.type === 'step-finish')
      .map(p => p.text)
      .join('\n') || msg.text || ''
    navigator.clipboard.writeText(text).catch(() => {})
  }

  function regenerateMessage(idx: number): string | null {
    const userMsg = messages.value[idx - 1]
    if (!userMsg || userMsg.role !== 'user') return null
    const text = userMsg.text || userMsg.parts?.map(p => p.text).join('') || ''
    if (!text) return null
    messages.value.splice(idx - 1, 2)
    return text
  }

  function clear() { messages.value = []; suggestions.value = [] }

  return { messages, suggestions, addUserMessage, addAssistantPlaceholder, appendDelta, addToolCall, addToolResult, addTrace, copyMessage, regenerateMessage, clear }
}

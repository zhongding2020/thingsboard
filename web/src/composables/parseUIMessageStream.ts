/** Parse Vercel AI SDK UI Message Stream v1 into UIMessage parts.
 *
 * Handles both streaming (text-delta) and non-streaming (tool-* events).
 */

export interface UIMessagePart {
  type: string
  text?: string
  toolName?: string
  toolCallId?: string
  state?: string
  input?: any
  output?: any
  data?: any
}

export interface UIMessage {
  id: string
  role: 'user' | 'assistant'
  content?: string
  parts: UIMessagePart[]
}

export async function streamToParts(
  body: ReadableStream<Uint8Array>,
): Promise<{ parts: UIMessagePart[] }> {
  const parts: UIMessagePart[] = []
  const textParts: UIMessagePart[] = []

  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buf = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })

    for (const line of buf.split('\n')) {
      const t = line.trim()

      // End-of-stream marker
      if (t === 'data: [DONE]') {
        // Close pending text part
        return { parts }
      }

      if (!t.startsWith('data: ')) continue

      try {
        const chunk = JSON.parse(t.slice(6))
        const type: string = chunk.type

        if (type === 'text-start') {
          const textPart: UIMessagePart = { type: 'text', text: '' }
          textParts.push(textPart)
        } else if (type === 'text-delta') {
          // Accumulate text to the most recent text part
          if (textParts.length > 0) {
            textParts[textParts.length - 1].text += chunk.delta || ''
          }
        } else if (type === 'tool-input-start') {
          const toolPart: UIMessagePart = {
            type: `tool-${chunk.toolName}`,
            toolName: chunk.toolName,
            toolCallId: chunk.toolCallId,
            state: 'input-streaming',
          }
          parts.push(toolPart)
        } else if (type === 'tool-input-available') {
          // Find the matching tool part and set its input
          const toolPart = parts.find(
            (p) => p.toolCallId === chunk.toolCallId && p.state === 'input-streaming',
          )
          if (toolPart) {
            toolPart.input = chunk.input
            toolPart.state = 'input-available'
          }
        } else if (type === 'tool-output-available') {
          const toolPart = parts.find(
            (p) => p.toolCallId === chunk.toolCallId && p.state !== 'output-available',
          )
          if (toolPart) {
            toolPart.output = chunk.output
            toolPart.state = 'output-available'
          } else {
            // Tool result without preceding input — standalone tool output
            parts.push({
              type: 'tool-output',
              toolName: chunk.toolName,
              toolCallId: chunk.toolCallId,
              state: 'output-available',
              output: chunk.output,
            })
          }
        }
      } catch {
        // Skip malformed JSON
      }
    }
  }

  // Flush any buffered text parts
  parts.unshift(...textParts)

  return { parts }
}

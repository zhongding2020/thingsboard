import { createOpencodeClient, type OpencodeClient } from '@opencode-ai/sdk'

const BASE_URL = import.meta.env.VITE_OPENCODE_URL || 'http://localhost:5100'

let _client: OpencodeClient | null = null

export function getClient(): OpencodeClient {
  if (!_client) {
    _client = createOpencodeClient({ baseUrl: BASE_URL })
  }
  return _client
}

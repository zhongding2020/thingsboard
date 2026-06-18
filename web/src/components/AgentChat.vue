<template>
  <div>
    <FloatingButton @click="visible = !visible" />
    <AgentSidebar :visible="visible" :maximized="maximized" @close="visible = false">
      <AgentHeader
        :currentModel="currentModel" :models="models"
        :processTypes="session.processTypes.value" :currentProcessType="session.currentProcessType.value"
        :showSessions="showSessions" :maximized="maximized"
        @switchModel="currentModel = $event"
        @switchProcess="(v: string) => { session.currentProcessType.value = v; onNewSession() }"
        @toggleSessions="showSessions = !showSessions"
        @newSession="onNewSession"
        @toggleMaximize="maximized = !maximized"
        @close="visible = false"
      />
      <div class="agent-messages">
        <SessionList
          v-if="showSessions"
          :sessions="session.sessions.value" :activeId="session.sessionId.value"
          @select="(id: string) => { onSwitchSession(id); showSessions = false }"
          @delete="onDeleteSession"
        />
        <ChatView v-else />
      </div>
    </AgentSidebar>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import FloatingButton from './agent/FloatingButton.vue'
import AgentSidebar from './agent/AgentSidebar.vue'
import AgentHeader from './agent/AgentHeader.vue'
import SessionList from './agent/SessionList.vue'
import ChatView from './agent/ChatView.vue'
import { useChatSession } from '@/composables/useChatSession'
import { useChatMessages } from '@/composables/useChatMessages'
import { useChatStream } from '@/composables/useChatStream'
import { listProcesses } from '@/api/agent'

const visible = ref(false)
const maximized = ref(false)
const showSessions = ref(false)
const currentModel = ref('deepseek-v4-flash')

const models = [
  { label: 'DeepSeek V4 Flash', value: 'deepseek-v4-flash' },
  { label: 'DeepSeek V4 Pro', value: 'deepseek-v4-pro' },
  { label: 'DeepSeek V3.2', value: 'deepseek-v3.2' },
  { label: 'Ark Code Latest', value: 'ark-code-latest' },
]

const session = useChatSession()
const messages = useChatMessages()
const stream = useChatStream()

onMounted(async () => {
  session.processTypes.value = await listProcesses()
  await session.refreshSessions()
  const saved = sessionStorage.getItem('opencode-session')
  if (saved && session.sessions.value.some(s => s.id === saved)) {
    session.sessionId.value = saved
    const history = await session.loadHistory()
    if (history.length) messages.messages.value = history
  } else if (!session.sessionId.value && session.sessions.value.length) {
    session.sessionId.value = session.sessions.value[0].id
    const history = await session.loadHistory()
    if (history.length) messages.messages.value = history
  }
})

onUnmounted(() => { stream.cancel() })

async function onNewSession() {
  sessionStorage.removeItem('opencode-session')
  await session.newSession()
  messages.clear()
}

function onSwitchSession(id: string) {
  session.switchSession(id)
  messages.clear()
  session.loadHistory().then((ms: any[]) => {
    if (ms.length) messages.messages.value = ms
  })
}

function onDeleteSession(id: string) {
  session.deleteSession(id)
  if (session.sessionId.value === id) messages.clear()
}
</script>

<style scoped>
.agent-messages { flex: 1; overflow-y: auto; display: flex; flex-direction: column; }
</style>

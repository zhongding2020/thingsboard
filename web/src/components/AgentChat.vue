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
import { ref, onMounted } from 'vue'
import FloatingButton from './agent/FloatingButton.vue'
import AgentSidebar from './agent/AgentSidebar.vue'
import AgentHeader from './agent/AgentHeader.vue'
import SessionList from './agent/SessionList.vue'
import ChatView from './agent/ChatView.vue'
import { useChatSession } from '@/composables/useChatSession'
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

onMounted(async () => {
  session.processTypes.value = await listProcesses()
  await session.refreshSessions()
})

async function onNewSession() {
  sessionStorage.removeItem('opencode-session')
  await session.newSession()
}

function onSwitchSession(id: string) {
  session.switchSession(id)
}

function onDeleteSession(id: string) {
  session.deleteSession(id)
}
</script>

<style scoped>
.agent-messages { flex: 1; overflow-y: auto; display: flex; flex-direction: column; }
</style>

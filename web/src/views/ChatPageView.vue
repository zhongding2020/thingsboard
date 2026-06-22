<template>
  <div class="flex h-screen bg-white dark:bg-gray-950">
    <!-- Left sidebar -->
    <aside class="w-72 flex-shrink-0 border-r border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 flex flex-col">
      <ThreadPicker
        :sessions="sessions"
        :activeId="sessionId"
        @select="switchSession"
        @delete="deleteSession"
        @new="newSession"
      />
    </aside>
    <!-- Main chat area -->
    <main class="flex-1 flex flex-col min-w-0">
      <ChatView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import ThreadPicker from '@/components/agent/ThreadPicker.vue'
import ChatView from '@/components/agent/ChatView.vue'
import { useChatSession } from '@/composables/useChatSession'

const { sessionId, sessions, refreshSessions, newSession, switchSession, deleteSession } = useChatSession()

onMounted(() => {
  refreshSessions()
})
</script>

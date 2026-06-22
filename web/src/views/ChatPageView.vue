<template>
  <div class="flex h-screen bg-white dark:bg-gray-950">
    <!-- Left sidebar -->
    <aside class="w-72 flex-shrink-0 border-r border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 flex flex-col">
      <div class="flex items-center justify-between px-3 py-2 border-b border-gray-200 dark:border-gray-700">
        <span class="text-xs font-semibold text-gray-500 dark:text-gray-400">会话</span>
        <button
          class="p-1 rounded-md text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer"
          @click="theme.toggle()"
          :title="theme.isDark.value ? '浅色模式' : '深色模式'"
        >
          <svg v-if="theme.isDark.value" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3a7 7 0 0 0 9.79 9.79z"/></svg>
        </button>
      </div>
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
import { useTheme } from '@/composables/useTheme'

const theme = useTheme()
const { sessionId, sessions, refreshSessions, newSession, switchSession, deleteSession } = useChatSession()

onMounted(() => {
  refreshSessions()
})
</script>

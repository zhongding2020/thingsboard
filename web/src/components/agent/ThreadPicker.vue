<template>
  <div class="flex flex-col h-full">
    <!-- Search box -->
    <div class="px-3 pt-3 pb-2">
      <div class="relative">
        <svg
          class="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 dark:text-slate-500 pointer-events-none"
          viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
        >
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.35-4.35" />
        </svg>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="搜索会话..."
          class="w-full pl-8 pr-3 py-1.5 text-sm rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500 transition-colors"
        />
      </div>
    </div>

    <!-- New session button -->
    <div class="px-3 pb-2">
      <button
        class="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border border-dashed border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-400 hover:border-indigo-400 dark:hover:border-indigo-500 hover:text-indigo-600 dark:hover:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-900/20 transition-colors"
        @click="$emit('new')"
      >
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 5v14M5 12h14" />
        </svg>
        新建会话
      </button>
    </div>

    <!-- Session list -->
    <div class="flex-1 overflow-y-auto px-2 pb-2">
      <div
        v-for="s in filteredSessions"
        :key="s.id"
        class="group flex items-center gap-2.5 px-2.5 py-2 rounded-lg cursor-pointer transition-colors"
        :class="s.id === activeId
          ? 'bg-indigo-50 dark:bg-indigo-900/25 text-indigo-700 dark:text-indigo-300'
          : 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'"
        @click="$emit('select', s.id)"
      >
        <!-- Chat icon -->
        <svg
          class="w-4 h-4 flex-shrink-0"
          :class="s.id === activeId ? 'text-indigo-500 dark:text-indigo-400' : 'text-slate-400 dark:text-slate-500'"
          viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
        >
          <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
        </svg>

        <!-- Session title -->
        <span class="flex-1 text-sm truncate leading-tight">
          {{ s.title || '新会话' }}
        </span>

        <!-- Delete button - visible on hover -->
        <button
          class="flex-shrink-0 p-1 rounded-md opacity-0 group-hover:opacity-100 text-slate-400 dark:text-slate-500 hover:text-red-500 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-all"
          title="删除会话"
          @click.stop="$emit('delete', s.id)"
        >
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 6h18M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
            <line x1="10" y1="11" x2="10" y2="17" />
            <line x1="14" y1="11" x2="14" y2="17" />
          </svg>
        </button>
      </div>

      <!-- Empty state -->
      <div
        v-if="filteredSessions.length === 0"
        class="text-center py-10 text-sm text-slate-400 dark:text-slate-500"
      >
        <svg class="w-10 h-10 mx-auto mb-3 opacity-40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
        </svg>
        <p>{{ searchQuery ? '无匹配会话' : '暂无会话记录' }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

interface SessionItem { id: string; title?: string }

const props = defineProps<{ sessions: SessionItem[]; activeId: string }>()
defineEmits<{ select: [id: string]; delete: [id: string]; new: [] }>()

const searchQuery = ref('')

const filteredSessions = computed(() => {
  if (!searchQuery.value.trim()) return props.sessions
  const q = searchQuery.value.trim().toLowerCase()
  return props.sessions.filter(
    s => (s.title || '新会话').toLowerCase().includes(q) || s.id.toLowerCase().includes(q),
  )
})
</script>

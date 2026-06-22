<template>
  <div class="flex items-center justify-between px-3.5 py-2.5 border-b border-gray-200 dark:border-gray-700 shrink-0 gap-2">
    <!-- Left: model dropdown -->
    <div class="relative">
      <button
        class="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 cursor-pointer"
        @click="showModelMenu = !showModelMenu"
        @blur="onBlurModelMenu"
      >
        {{ currentModelLabel }}
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
      </button>
      <div
        v-if="showModelMenu"
        class="absolute top-full left-0 mt-1 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-50 py-1 min-w-[140px]"
      >
        <button
          v-for="m in models"
          :key="m.value"
          class="block w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-indigo-50 dark:hover:bg-indigo-950"
          :class="{ 'text-indigo-600 dark:text-indigo-400 font-medium': m.value === currentModel }"
          @mousedown.prevent="$emit('switchModel', m.value)"
        >{{ m.label }}</button>
      </div>
    </div>

    <!-- Center: AI title -->
    <div class="flex items-center gap-1.5 text-sm font-semibold text-indigo-500">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
        <path d="M12 3l2.5 5.5L20 9.5l-4 4 .5 5.5L12 16l-4.5 3 .5-5.5-4-4L9.5 8.5z"/>
      </svg>
      AI
    </div>

    <!-- Right: action buttons -->
    <div class="flex items-center gap-0.5">
      <button
        class="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md cursor-pointer"
        @click="$emit('toggleSessions')"
        :title="showSessions ? '返回' : '历史'"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
          <circle cx="12" cy="12" r="10"/>
          <path d="M12 6v6l4 2"/>
        </svg>
      </button>
      <button
        class="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md cursor-pointer"
        @click="$emit('newSession')"
        title="新建"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <path d="M12 5v14M5 12h14"/>
        </svg>
      </button>
      <button
        class="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md cursor-pointer"
        @click="$emit('toggleMaximize')"
        :title="maximized ? '还原' : '最大化'"
      >
        <svg v-if="!maximized" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="4" y="4" width="16" height="16" rx="2"/>
        </svg>
        <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="8" y="8" width="12" height="12" rx="2"/>
          <rect x="4" y="4" width="12" height="12" rx="2"/>
        </svg>
      </button>
      <!-- Theme toggle -->
      <button
        class="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md cursor-pointer"
        @click="theme.toggle()"
        :title="theme.isDark.value ? '浅色模式' : '深色模式'"
      >
        <!-- Sun icon (shown in dark mode → switch to light) -->
        <svg v-if="theme.isDark.value" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <circle cx="12" cy="12" r="5"/>
          <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
        </svg>
        <!-- Moon icon (shown in light mode → switch to dark) -->
        <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3a7 7 0 0 0 9.79 9.79z"/>
        </svg>
      </button>
      <button
        class="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md cursor-pointer"
        @click="$emit('close')"
        title="关闭"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <path d="M18 6L6 18M6 6l12 12"/>
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useTheme } from '@/composables/useTheme'

const theme = useTheme()

interface Model { label: string; value: string }
interface ProcessType { process_type: string; display_name: string }

const props = defineProps<{
  currentModel: string
  models: Model[]
  processTypes: ProcessType[]
  currentProcessType: string
  showSessions: boolean
  maximized: boolean
}>()

defineEmits<{
  switchModel: [val: string]
  switchProcess: [val: string]
  toggleSessions: []
  newSession: []
  toggleMaximize: []
  close: []
}>()

const showModelMenu = ref(false)
const currentModelLabel = computed(() => props.models.find(m => m.value === props.currentModel)?.label || '')

function onBlurModelMenu() {
  setTimeout(() => { showModelMenu.value = false }, 150)
}
</script>

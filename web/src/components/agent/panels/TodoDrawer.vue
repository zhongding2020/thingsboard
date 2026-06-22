<template>
  <div
    class="h-full flex flex-col bg-white dark:bg-gray-950"
  >
    <!-- Header -->
    <div class="flex items-center justify-between px-3 py-2.5 border-b border-gray-200 dark:border-gray-800">
      <span class="text-sm font-medium text-gray-700 dark:text-gray-300">✅ 待办</span>
      <button
        class="p-0.5 rounded text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 bg-transparent border-none cursor-pointer"
        @click="$emit('close')"
      >
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
    </div>

    <!-- Todo list -->
    <div class="flex-1 overflow-y-auto">
      <template v-if="todos.length > 0">
        <div
          v-for="item in todos"
          :key="item.id"
          class="flex items-start gap-2.5 px-3 py-2 border-b border-gray-50 dark:border-gray-800/50"
        >
          <!-- Checkbox indicator -->
          <span
            class="flex-shrink-0 mt-0.5 w-4 h-4 rounded border flex items-center justify-center text-[10px]"
            :class="item.done
              ? 'bg-green-500 border-green-500 text-white'
              : 'border-gray-300 dark:border-gray-600 text-transparent'"
          >
            <svg
              v-if="item.done"
              class="w-2.5 h-2.5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="3"
            >
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </span>
          <!-- Text -->
          <span
            class="text-xs leading-relaxed"
            :class="item.done
              ? 'line-through text-gray-400 dark:text-gray-500'
              : 'text-gray-700 dark:text-gray-300'"
          >{{ item.text }}</span>
        </div>
      </template>

      <!-- Empty state -->
      <div v-else class="p-4 text-xs text-gray-400 dark:text-gray-600 text-center">
        暂无待办事项
      </div>
    </div>

    <!-- Footer: progress summary -->
    <div
      v-if="todos.length > 0"
      class="px-3 py-1.5 border-t border-gray-100 dark:border-gray-800 text-[10px]"
      :class="doneCount === todos.length ? 'text-green-500' : 'text-gray-400'"
    >
      {{ doneCount }}/{{ todos.length }} 已完成
      <span v-if="doneCount === todos.length"> 🎉</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { TodoItem } from '@/composables/useAgentStream'

const props = defineProps<{
  todos: TodoItem[]
}>()

defineEmits<{ close: [] }>()

const doneCount = computed(() => props.todos.filter((t) => t.done).length)
</script>

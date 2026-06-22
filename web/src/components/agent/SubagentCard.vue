<template>
  <div
    class="my-1 border rounded-lg overflow-hidden max-w-[95%]"
    :class="borderClass"
  >
    <!-- Header -->
    <div
      class="flex items-center gap-2 px-3 py-2 cursor-pointer select-none"
      :class="headerClass"
      @click="isOpen = !isOpen"
    >
      <!-- Status dot -->
      <span
        class="w-2 h-2 rounded-full flex-shrink-0"
        :class="dotClass"
      />
      <span class="text-xs font-medium flex-1 truncate">{{ name }}</span>
      <!-- Chevron -->
      <svg
        class="w-3.5 h-3.5 transition-transform duration-200 flex-shrink-0"
        :class="{ 'rotate-180': !isOpen }"
        viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
      >
        <path d="M6 9l6 6 6-6" />
      </svg>
    </div>
    <!-- Body -->
    <div v-if="isOpen" class="px-3 pb-2">
      <div v-if="status === 'error'" class="text-red-600 dark:text-red-400 text-xs leading-relaxed whitespace-pre-wrap">{{ content }}</div>
      <TextBlock v-else :text="content" :isStreaming="status === 'running'" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { computed } from 'vue'
import TextBlock from './TextBlock.vue'

const props = defineProps<{
  name: string
  content: string
  status: 'running' | 'done' | 'error'
  open: boolean
}>()

const isOpen = ref(props.open)

const borderClass = computed(() => {
  switch (props.status) {
    case 'running':
      return 'border-green-200 dark:border-green-800 bg-green-50/50 dark:bg-green-900/20'
    case 'done':
      return 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900'
    case 'error':
      return 'border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30'
  }
})

const headerClass = computed(() => {
  switch (props.status) {
    case 'running':
      return 'text-green-700 dark:text-green-300'
    case 'done':
      return 'text-gray-500 dark:text-gray-400'
    case 'error':
      return 'text-red-600 dark:text-red-400'
  }
})

const dotClass = computed(() => {
  switch (props.status) {
    case 'running':
      return 'bg-green-500 animate-pulse'
    case 'done':
      return 'bg-green-500'
    case 'error':
      return 'bg-red-500'
  }
})
</script>

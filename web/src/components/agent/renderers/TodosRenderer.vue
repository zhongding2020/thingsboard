<template>
  <div>
    <template v-if="todoItems.length > 0">
      <div
        v-for="item in todoItems"
        :key="item.id"
        class="flex items-start gap-2 py-0.5"
      >
        <!-- Checkbox -->
        <span
          class="flex-shrink-0 mt-0.5 w-4 h-4 rounded border flex items-center justify-center text-[10px]"
          :class="item.done
            ? 'bg-green-500 border-green-500 text-white'
            : 'border-gray-300 dark:border-gray-600 text-transparent'"
        >
          <svg v-if="item.done" class="w-2.5 h-2.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
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
    <div v-else class="markdown-body" v-html="rendered" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'

interface TodoEntry {
  id: string
  text: string
  done: boolean
}

const props = defineProps<{ data: string }>()

const todoItems = computed<TodoEntry[]>(() => {
  const text = props.data || ''
  const lines = text.split('\n')
  const items: TodoEntry[] = []

  for (const line of lines) {
    // Match `- [ ] text` or `- [x] text` or `* [ ]` or `* [x]`
    const match = line.match(/^[-*]\s+\[([ xX])\]\s+(.+)$/)
    if (match) {
      items.push({
        id: `todo-${items.length}`,
        done: match[1].toLowerCase() === 'x',
        text: match[2].trim(),
      })
    }
  }

  return items
})

const rendered = computed(() =>
  marked.parse(props.data || '', { breaks: true, gfm: true }) as string
)
</script>

<style scoped>
.markdown-body :deep(p) { margin: 0 0 4px; font-size: 12px; }
.markdown-body :deep(p:last-child) { margin-bottom: 0; }
.markdown-body :deep(code) { font-size: 11px; background: #f1f5f9; padding: 1px 4px; border-radius: 3px; }
</style>

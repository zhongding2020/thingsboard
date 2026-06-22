<template>
  <div
    class="h-full flex flex-col bg-white dark:bg-gray-950 border-l border-gray-200 dark:border-gray-800"
  >
    <!-- Header -->
    <div class="flex items-center justify-between px-3 py-2.5 border-b border-gray-200 dark:border-gray-800">
      <span class="text-sm font-medium text-gray-700 dark:text-gray-300">📁 文件</span>
      <button
        class="p-0.5 rounded text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 bg-transparent border-none cursor-pointer"
        @click="$emit('close')"
      >
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
    </div>

    <!-- File list -->
    <div class="flex-1 overflow-y-auto">
      <template v-if="parsedFiles.length > 0">
        <div
          v-for="(f, i) in parsedFiles"
          :key="i"
          class="border-b border-gray-100 dark:border-gray-800"
        >
          <!-- File entry header (click to toggle) -->
          <button
            class="w-full flex items-center gap-2 px-3 py-2 text-left bg-transparent border-none cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-900 transition-colors"
            @click="toggle(i)"
          >
            <!-- Chevron -->
            <svg
              class="w-3 h-3 flex-shrink-0 text-gray-400 transition-transform duration-150"
              :class="{ 'rotate-90': expanded[i] }"
              viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            >
              <polyline points="9 18 15 12 9 6" />
            </svg>
            <!-- File icon -->
            <svg class="w-3.5 h-3.5 flex-shrink-0 text-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            <!-- File path -->
            <span class="flex-1 text-[11px] font-mono text-gray-600 dark:text-gray-400 truncate">{{ f.path }}</span>
            <!-- Language badge -->
            <span
              v-if="f.language"
              class="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-400 flex-shrink-0"
            >{{ f.language }}</span>
          </button>

          <!-- File content (expandable) -->
          <div v-if="expanded[i]" class="px-2 pb-2">
            <pre
              class="m-0 p-2 text-[11px] leading-relaxed rounded-md bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 overflow-x-auto max-h-64 overflow-y-auto"
              :class="f.language ? 'language-' + f.language : ''"
            ><code>{{ f.content }}</code></pre>
          </div>
        </div>
      </template>

      <!-- Empty state -->
      <div v-else class="p-4 text-xs text-gray-400 dark:text-gray-600 text-center">
        暂无文件
      </div>
    </div>

    <!-- Footer: count -->
    <div
      v-if="parsedFiles.length > 0"
      class="px-3 py-1.5 border-t border-gray-100 dark:border-gray-800 text-[10px] text-gray-400"
    >{{ parsedFiles.length }} 个文件</div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive } from 'vue'
import type { ChatMessage } from '@/composables/useAgentStream'

interface ParsedFile {
  path: string
  language: string
  content: string
}

const props = defineProps<{
  messages: ChatMessage[]
}>()

defineEmits<{ close: [] }>()

// -------------------------------------------------------------------------
// Parse file entries from all assistant messages' tool call results
// -------------------------------------------------------------------------
const parsedFiles = computed<ParsedFile[]>(() => {
  const seen = new Set<string>()
  const files: ParsedFile[] = []

  for (const msg of props.messages) {
    if (msg.role !== 'assistant') continue
    const tcs = msg.toolCalls || []
    for (const tc of tcs) {
      if (tc.status !== 'done' || !tc.result) continue
      if (!isFileTool(tc.name)) continue
      const parsed = parseResult(tc.result)
      for (const pf of parsed) {
        if (!seen.has(pf.path)) {
          seen.add(pf.path)
          files.push(pf)
        }
      }
    }
  }

  return files
})

function isFileTool(name: string): boolean {
  return /file|list_files|read|write|edit/i.test(name)
}

function parseResult(text: string): ParsedFile[] {
  const files: ParsedFile[] = []
  const lines = text.split('\n')

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    // Check for file path comment preceding a code block
    const pathMatch = line.match(
      /^(?:#|\/\/|\/\*)\s*(?:file|path|filename):\s*(.+?)(?:\s*\*\/)?$/i,
    )
    let filePath = pathMatch ? pathMatch[1].trim() : ''

    // Check for fenced code block start
    const codeMatch = line.match(/^```(\w+)?$/)
    if (codeMatch) {
      const language = codeMatch[1] || ''
      const codeLines: string[] = []
      let j = i + 1
      while (j < lines.length && !lines[j].startsWith('```')) {
        codeLines.push(lines[j])
        j++
      }
      const content = codeLines.join('\n')

      if (!filePath && codeLines.length > 0) {
        const fnMatch = codeLines[0].match(
          /^(?:#|\/\/)\s*(?:file|path|filename):\s*(.+?)$/i,
        )
        if (fnMatch) filePath = fnMatch[1].trim()
      }

      files.push({ path: filePath || `code-block-${i}`, language, content })
      i = j
    }
  }

  return files
}

// -------------------------------------------------------------------------
// Expand / collapse state
// -------------------------------------------------------------------------
const expanded = reactive<Record<number, boolean>>({})

function toggle(i: number) {
  expanded[i] = !expanded[i]
}
</script>

<template>
  <div>
    <template v-if="parsedFiles.length > 0">
      <div v-for="(f, i) in parsedFiles" :key="i" class="mb-2 last:mb-0">
        <div class="flex items-center gap-1.5 mb-1 text-gray-500 dark:text-gray-400">
          <!-- File icon -->
          <svg class="w-3.5 h-3.5 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
          </svg>
          <span class="text-[11px] font-mono font-medium truncate">{{ f.path }}</span>
        </div>
        <pre
          v-if="f.language"
          class="m-0 p-2 text-[11px] leading-relaxed rounded-md bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 overflow-x-auto"
          :class="f.language ? 'language-' + f.language : ''"
        ><code>{{ f.content }}</code></pre>
        <pre
          v-else
          class="m-0 p-2 text-[11px] leading-relaxed rounded-md bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 overflow-x-auto whitespace-pre-wrap"
        ><code>{{ f.content }}</code></pre>
      </div>
    </template>
    <div v-else class="markdown-body" v-html="rendered" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'

interface ParsedFile {
  path: string
  language: string
  content: string
}

const props = defineProps<{ data: string }>()

const parsedFiles = computed<ParsedFile[]>(() => {
  const files: ParsedFile[] = []
  const text = props.data || ''

  // Match code blocks: optional file path comment on previous line, then ```language\ncontent\n```
  // Pattern: optional "file:" or "path:" prefix comment, then a fenced code block
  const lines = text.split('\n')
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    // Check for file path comment
    const pathMatch = line.match(/^(?:#|\/\/|\/\*)\s*(?:file|path|filename):\s*(.+?)(?:\s*\*\/)?$/i)
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
        // Try to extract filename from first line comment
        const fnMatch = codeLines[0].match(/^(?:#|\/\/)\s*(?:file|path|filename):\s*(.+?)$/i)
        if (fnMatch) {
          filePath = fnMatch[1].trim()
        }
      }

      files.push({ path: filePath || `code-block-${i}`, language, content })
      i = j // skip to end of code block
    }
  }

  return files
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

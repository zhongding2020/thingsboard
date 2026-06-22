<template>
  <div>
    <template v-if="searchResults.length > 0">
      <div
        v-for="(r, i) in searchResults"
        :key="i"
        class="mb-1.5 last:mb-0 border border-gray-100 dark:border-gray-800 rounded-md px-2.5 py-1.5 bg-gray-50 dark:bg-gray-800/50"
      >
        <div class="text-[11px] font-medium text-gray-700 dark:text-gray-200 mb-0.5" v-html="highlightTitle(r.title)" />
        <div v-if="r.snippet" class="text-[11px] text-gray-500 dark:text-gray-400 leading-relaxed" v-html="highlightSnippet(r.snippet)" />
      </div>
    </template>
    <div v-else class="markdown-body" v-html="rendered" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'

interface SearchResult {
  title: string
  snippet: string
}

const props = defineProps<{ data: string }>()

const searchResults = computed<SearchResult[]>(() => {
  const text = props.data || ''

  // Try JSON first
  try {
    const parsed = JSON.parse(text)
    if (Array.isArray(parsed)) {
      return parsed.map((item: Record<string, unknown>) => ({
        title: String(item.title || item.name || item.id || ''),
        snippet: String(item.snippet || item.summary || item.description || item.body || ''),
      }))
    }
    if (parsed && typeof parsed === 'object') {
      // Single result object
      const title = String((parsed as Record<string, unknown>).title || (parsed as Record<string, unknown>).name || '')
      const snippet = String((parsed as Record<string, unknown>).snippet || (parsed as Record<string, unknown>).summary || (parsed as Record<string, unknown>).content || '')
      if (title) return [{ title, snippet }]

      // Try results/data/items array properties
      for (const key of ['results', 'data', 'items', 'matches']) {
        const arr = (parsed as Record<string, unknown>)[key]
        if (Array.isArray(arr)) {
          return (arr as Array<Record<string, unknown>>).map(item => ({
            title: String(item.title || item.name || item.id || ''),
            snippet: String(item.snippet || item.summary || item.description || item.body || ''),
          }))
        }
      }
    }
  } catch {
    // Not JSON, parse as markdown
  }

  // Try markdown list
  const results: SearchResult[] = []
  const lines = text.split('\n')
  let current: SearchResult | null = null

  for (const line of lines) {
    const listMatch = line.match(/^[-*]\s+\*{0,2}(.+?)\*{0,2}\s*(?::\s*(.*))?$/)
    if (listMatch) {
      if (current) results.push(current)
      current = { title: listMatch[1].replace(/[*_]/g, ''), snippet: listMatch[2] || '' }
      continue
    }

    // Numbered list
    const numMatch = line.match(/^\d+[.)]\s+\*{0,2}(.+?)\*{0,2}\s*(?::\s*(.*))?$/)
    if (numMatch) {
      if (current) results.push(current)
      current = { title: numMatch[1].replace(/[*_]/g, ''), snippet: numMatch[2] || '' }
      continue
    }

    // Line starting with **Title**:
    const boldMatch = line.match(/^\*{2}(.+?)\*{2}\s*(?::\s*(.*))?$/)
    if (boldMatch) {
      if (current) results.push(current)
      current = { title: boldMatch[1], snippet: boldMatch[2] || '' }
      continue
    }

    // Indented continuation (append to previous snippet)
    if (current && line.match(/^\s{2,}/)) {
      if (current.snippet) current.snippet += '\n' + line.trim()
      else current.snippet = line.trim()
    }
  }
  if (current) results.push(current)

  return results
})

function highlightTitle(text: string): string {
  // Basic markdown → HTML for bold/italic in titles
  return text
    .replace(/\*\*(.+?)\*\*/g, '<span class="font-semibold text-blue-600 dark:text-blue-400">$1</span>')
    .replace(/\*(.+?)\*/g, '<span class="italic">$1</span>')
}

function highlightSnippet(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<span class="font-semibold text-blue-600 dark:text-blue-400">$1</span>')
    .replace(/\*(.+?)\*/g, '<span class="italic">$1</span>')
}

const rendered = computed(() =>
  marked.parse(props.data || '', { breaks: true, gfm: true }) as string
)
</script>

<style scoped>
.markdown-body :deep(p) { margin: 0 0 4px; font-size: 12px; }
.markdown-body :deep(p:last-child) { margin-bottom: 0; }
.markdown-body :deep(code) { font-size: 11px; background: #f1f5f9; padding: 1px 4px; border-radius: 3px; }
</style>

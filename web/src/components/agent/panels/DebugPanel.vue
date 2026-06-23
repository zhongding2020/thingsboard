<template>
  <div class="flex flex-col border-t border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900/50">
    <!-- Header bar: click to toggle -->
    <button
      class="flex items-center gap-2 px-3 py-2 text-xs cursor-pointer border-none bg-transparent hover:bg-gray-100 dark:hover:bg-gray-800/50 transition-colors"
      @click="expanded = !expanded"
    >
      <svg
        class="w-3.5 h-3.5 text-gray-400 transition-transform"
        :class="{ 'rotate-90': expanded }"
        viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
      >
        <polyline points="9 18 15 12 9 6" />
      </svg>
      <span class="font-medium text-gray-600 dark:text-gray-400">
        Debug ({{ visibleCount }} 事件)
      </span>
      <span v-if="!expanded" class="text-gray-400 dark:text-gray-600">
        {{ recentSummary }}
      </span>
    </button>

    <!-- Expanded body -->
    <div v-if="expanded" class="flex flex-col">
      <!-- Filter bar -->
      <div class="flex items-center gap-1.5 px-3 py-1.5 border-b border-gray-200 dark:border-gray-800">
        <button
          v-for="cat in categories"
          :key="cat.key"
          class="px-2 py-0.5 text-[10px] rounded-full border cursor-pointer transition-colors"
          :class="filter[cat.key]
            ? cat.activeClass
            : 'border-gray-200 dark:border-gray-700 text-gray-400 dark:text-gray-600 bg-transparent'"
          @click="filter[cat.key] = !filter[cat.key]"
        >{{ cat.label }}</button>
        <div class="flex-1" />
        <button
          class="px-2 py-0.5 text-[10px] rounded border-none cursor-pointer bg-transparent text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
          @click="clearEvents"
        >清空</button>
      </div>

      <!-- Event list -->
      <div ref="listRef" class="overflow-y-auto font-mono text-xs leading-relaxed" style="max-height: 400px">
        <template v-if="visibleEvents.length > 0">
          <div
            v-for="(evt, i) in visibleEvents"
            :key="i"
            class="border-b border-gray-100 dark:border-gray-800/40"
            :class="i % 2 === 0 ? 'bg-transparent' : 'bg-white/50 dark:bg-gray-950/30'"
          >
            <!-- Summary row — click to expand -->
            <div
              class="flex items-start gap-2 px-3 py-1 cursor-pointer select-none hover:bg-gray-100 dark:hover:bg-gray-800/30 transition-colors"
              @click="toggleEvent(i)"
            >
              <!-- Expand indicator -->
              <span class="flex-shrink-0 w-3 text-gray-300 dark:text-gray-600 transition-transform duration-150 mt-0.5"
                :class="{ 'rotate-90': expandedEvents.has(i) }">▸</span>
              <!-- Category badge -->
              <span
                class="flex-shrink-0 mt-0.5 px-1.5 py-px rounded text-[10px] font-medium"
                :class="categoryBadge(evt.type)"
              >{{ categoryLabel(evt.type) }}</span>
              <!-- Type -->
              <span class="flex-shrink-0 text-gray-500 dark:text-gray-400 min-w-[130px]">{{ evt.type }}</span>
              <!-- Name -->
              <span
                v-if="evt.name"
                class="flex-shrink-0 text-blue-500 dark:text-blue-400 truncate max-w-[140px]"
              >{{ evt.name }}</span>
              <!-- Preview snippet -->
              <span class="flex-1 text-gray-400 dark:text-gray-600 truncate text-[10px]">{{ payloadPreview(evt) }}</span>
              <!-- Time -->
              <span class="flex-shrink-0 text-gray-400 dark:text-gray-600 tabular-nums">{{ formatTime(evt.timestamp) }}</span>
            </div>

            <!-- Expanded detail -->
            <div v-if="expandedEvents.has(i)" class="px-8 pb-2">
              <pre
                class="m-0 p-2 rounded text-[10px] leading-relaxed whitespace-pre-wrap break-all max-h-[300px] overflow-y-auto"
                :class="evt.type === 'error'
                  ? 'bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-300 border border-red-100 dark:border-red-900/50'
                  : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400'"
              >{{ formatPayload(evt) }}</pre>
            </div>
          </div>
        </template>
        <div v-else class="px-4 py-6 text-center text-gray-400 dark:text-gray-600 text-xs">
          暂无事件 — 发送消息后自动记录
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface DebugEvent {
  type: string
  name?: string
  timestamp: number
  payload?: unknown
}

const props = defineProps<{
  events: DebugEvent[]
}>()

const emit = defineEmits<{ clear: [] }>()

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
const expanded = ref(false)
const expandedEvents = ref(new Set<number>())

function toggleEvent(i: number) {
  const next = new Set(expandedEvents.value)
  if (next.has(i)) {
    next.delete(i)
  } else {
    next.add(i)
  }
  expandedEvents.value = next
}

// ---------------------------------------------------------------------------
// Filter state
// ---------------------------------------------------------------------------
const filter = ref<Record<string, boolean>>({
  message: true,
  tool: true,
  subagent: true,
  thinking: false,
  system: true,
  error: true,
})

const categories = [
  { key: 'message', label: '消息', activeClass: 'bg-blue-100 dark:bg-blue-900/40 border-blue-300 dark:border-blue-700 text-blue-600 dark:text-blue-400' },
  { key: 'tool', label: '工具', activeClass: 'bg-blue-100 dark:bg-blue-900/40 border-blue-300 dark:border-blue-700 text-blue-600 dark:text-blue-400' },
  { key: 'subagent', label: '子代理', activeClass: 'bg-green-100 dark:bg-green-900/40 border-green-300 dark:border-green-700 text-green-600 dark:text-green-400' },
  { key: 'thinking', label: '思考', activeClass: 'bg-purple-100 dark:bg-purple-900/40 border-purple-300 dark:border-purple-700 text-purple-600 dark:text-purple-400' },
  { key: 'system', label: '系统', activeClass: 'bg-gray-200 dark:bg-gray-700 border-gray-400 dark:border-gray-600 text-gray-600 dark:text-gray-300' },
  { key: 'error', label: '错误', activeClass: 'bg-red-100 dark:bg-red-900/40 border-red-300 dark:border-red-700 text-red-600 dark:text-red-400' },
]

// ---------------------------------------------------------------------------
// Categorization
// ---------------------------------------------------------------------------
function eventCategory(type: string): string {
  if (type.startsWith('message.')) return 'message'
  if (type.startsWith('tool.')) return 'tool'
  if (type.startsWith('subagent.')) return 'subagent'
  if (type.startsWith('thinking.')) return 'thinking'
  if (type === 'error') return 'error'
  return 'system'
}

function categoryLabel(type: string): string {
  const map: Record<string, string> = {
    message: 'MSG',
    tool: 'TOOL',
    subagent: 'SUB',
    thinking: 'THK',
    system: 'SYS',
    error: 'ERR',
  }
  return map[eventCategory(type)] || 'SYS'
}

function categoryBadge(type: string): string {
  const map: Record<string, string> = {
    message: 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300',
    tool: 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300',
    subagent: 'bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300',
    thinking: 'bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300',
    system: 'bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300',
    error: 'bg-red-100 dark:bg-red-900/50 text-red-700 dark:text-red-300',
  }
  return map[eventCategory(type)] || 'bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300'
}

// ---------------------------------------------------------------------------
// Payload formatting
// ---------------------------------------------------------------------------
function payloadPreview(evt: DebugEvent): string {
  if (!evt.payload) return ''
  const p = evt.payload as Record<string, unknown>
  // Show most relevant field as preview
  if (evt.type === 'error') return p.message as string || ''
  if (evt.type === 'message.delta') return p.text as string || ''
  if (evt.type === 'tool.call') return `args: ${JSON.stringify(p.args || p)}`
  if (evt.type === 'tool.result') return (p.data as string || '').slice(0, 80)
  if (evt.type === 'interactive.prompt') return (p.action as Record<string, unknown>)?.title as string || ''
  return ''
}

function formatPayload(evt: DebugEvent): string {
  if (!evt.payload) return '(无 payload)'
  try {
    return JSON.stringify(evt.payload, null, 2)
  } catch {
    return String(evt.payload)
  }
}

// ---------------------------------------------------------------------------
// Computed
// ---------------------------------------------------------------------------
const visibleEvents = computed(() =>
  props.events.filter((e) => filter.value[eventCategory(e.type)])
)

const visibleCount = computed(() => visibleEvents.value.length)

const recentSummary = computed(() => {
  const total = props.events.length
  if (total === 0) return ''
  const last = props.events[total - 1]
  return `${last.type}${last.name ? ` (${last.name})` : ''}`
})

// ---------------------------------------------------------------------------
// Time formatting (relative to first event)
// ---------------------------------------------------------------------------
const t0 = computed(() => {
  if (props.events.length === 0) return 0
  return props.events[0].timestamp
})

function formatTime(ts: number): string {
  const delta = (ts - t0.value) / 1000
  return `+${delta.toFixed(2)}s`
}

// ---------------------------------------------------------------------------
// Clear
// ---------------------------------------------------------------------------
function clearEvents() {
  expandedEvents.value = new Set()
  emit('clear')
}

// ---------------------------------------------------------------------------
// Auto-scroll
// ---------------------------------------------------------------------------
const listRef = ref<HTMLDivElement>()

watch(
  () => props.events.length,
  () => {
    nextTick(() => {
      if (listRef.value) {
        listRef.value.scrollTop = listRef.value.scrollHeight
      }
    })
  }
)
</script>

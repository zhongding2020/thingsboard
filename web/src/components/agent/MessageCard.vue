<template>
  <div class="flex flex-col gap-1.5 group">
    <!-- User message -->
    <div
      v-if="msg.role === 'user'"
      class="self-end bg-indigo-500 text-white px-4 py-2.5 rounded-2xl rounded-br-sm max-w-[85%] text-sm leading-relaxed break-words"
    >
      {{ msg.content }}
    </div>

    <!-- Assistant message -->
    <template v-else>
      <!-- Thinking block -->
      <ThinkingBlock
        v-if="msg.thinking"
        :text="msg.thinking"
        :isStreaming="isStreaming && !msg.content"
      />

      <!-- Text content -->
      <div
        v-if="msg.content"
        class="self-start bg-gray-100 dark:bg-gray-800 px-4 py-2.5 rounded-2xl rounded-bl-sm max-w-[85%]"
      >
        <TextBlock :text="msg.content" :isStreaming="isStreaming" />
      </div>

      <!-- Tool calls -->
      <ToolCallCard
        v-for="(tc, j) in msg.toolCalls"
        :key="j"
        :tc="tc"
      />

      <!-- Subagent cards -->
      <SubagentCard
        v-for="(sa, k) in msg.subagents"
        :key="k"
        :name="sa.name"
        :content="sa.content"
        :status="sa.status"
        :open="sa.open"
      />

      <!-- Action buttons (only when not streaming) -->
      <div
        v-if="!isStreaming"
        class="flex gap-1.5 mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity self-start"
      >
        <button
          class="flex items-center gap-1 px-2 py-1 text-[11px] text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 bg-transparent border-none rounded cursor-pointer"
          @click="$emit('copy')"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
          复制
        </button>
        <button
          class="flex items-center gap-1 px-2 py-1 text-[11px] text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 bg-transparent border-none rounded cursor-pointer"
          @click="$emit('regenerate')"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 4v6h6"/><path d="M23 20v-6h-6"/><path d="M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15"/></svg>
          重新生成
        </button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import TextBlock from './TextBlock.vue'
import ThinkingBlock from './ThinkingBlock.vue'
import ToolCallCard from './ToolCallCard.vue'
import SubagentCard from './SubagentCard.vue'
import type { ChatMessage } from '@/composables/useAgentStream'

defineProps<{ msg: ChatMessage; isStreaming: boolean }>()
defineEmits<{ copy: []; regenerate: [] }>()
</script>

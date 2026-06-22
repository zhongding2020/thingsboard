<template>
  <div v-if="actions.length" class="flex flex-col gap-2 mt-2">
    <template v-for="action in actions" :key="action.id">
      <!-- Resolved state: show read-only summary -->
      <div
        v-if="action.status === 'resolved'"
        class="flex items-center gap-1.5 text-[11px] text-slate-500 dark:text-slate-400 px-2 py-1 rounded-lg bg-slate-100 dark:bg-slate-800/50"
      >
        <span>&#9989;</span>
        <span>{{ action.title }}：{{ resolvedLabel(action) }}</span>
      </div>
      <!-- Pending state: render interactive widget -->
      <div v-else class="border border-blue-200 dark:border-blue-700 rounded-xl bg-blue-50/30 dark:bg-blue-950/20 p-3">
        <p class="text-[11px] font-medium text-slate-700 dark:text-slate-200 mb-2">
          {{ action.title }}
        </p>
        <p v-if="action.description" class="text-[10px] text-slate-400 dark:text-slate-500 mb-2">
          {{ action.description }}
        </p>
        <ActionSelect
          v-if="action.type === 'select'"
          :action="action"
          @resolve="(v: unknown) => $emit('resolve', action.id, v)"
        />
        <ActionMultiSelect
          v-else-if="action.type === 'multi_select'"
          :action="action"
          @resolve="(v: unknown) => $emit('resolve', action.id, v)"
        />
        <ActionConfirm
          v-else-if="action.type === 'confirm'"
          :action="action"
          @resolve="(v: unknown) => $emit('resolve', action.id, v)"
        />
        <ActionInput
          v-else-if="action.type === 'input'"
          :action="action"
          @resolve="(v: unknown) => $emit('resolve', action.id, v)"
        />
        <ActionCascader
          v-else-if="action.type === 'cascader'"
          :action="action"
          @resolve="(v: unknown) => $emit('resolve', action.id, v)"
        />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { InteractiveAction } from '@/composables/useAgentStream'
import ActionSelect from './ActionSelect.vue'
import ActionMultiSelect from './ActionMultiSelect.vue'
import ActionConfirm from './ActionConfirm.vue'
import ActionInput from './ActionInput.vue'
import ActionCascader from './ActionCascader.vue'

defineProps<{ actions: InteractiveAction[] }>()
defineEmits<{ resolve: [actionId: string, value: unknown] }>()

function resolvedLabel(action: InteractiveAction): string {
  if (action.type === 'confirm') {
    return (action as any)._resolvedValue ? action.confirmText || '已确认' : action.cancelText || '已取消'
  }
  return (action as any)._resolvedLabel || '已选择'
}
</script>

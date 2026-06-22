<template>
  <div class="flex flex-col gap-2">
    <div v-for="level in action.cascaderLevels" :key="level.key" class="flex flex-col gap-1">
      <span class="text-[10px] text-slate-400 dark:text-slate-500">{{ level.label }}</span>
      <el-select
        :model-value="selections[level.key]"
        :placeholder="`请选择${level.label}`"
        size="small"
        @change="(val: string) => onLevelChange(level.key, val, level.options || [])"
      >
        <el-option
          v-for="opt in level.options"
          :key="opt.value"
          :label="opt.label"
          :value="opt.value"
          :disabled="opt.disabled"
        />
      </el-select>
    </div>
    <button
      :disabled="!allLevelsFilled"
      class="self-start px-3 py-1 text-[11px] rounded-md bg-blue-500 hover:bg-blue-600 disabled:opacity-40 text-white border-none cursor-pointer transition-colors"
      @click="submit"
    >确认选择</button>
  </div>
</template>

<script setup lang="ts">
import { reactive, computed } from 'vue'
import type { InteractiveAction } from '@/composables/useAgentStream'

const props = defineProps<{ action: InteractiveAction }>()
const emit = defineEmits<{ resolve: [value: unknown] }>()

const selections = reactive<Record<string, string>>({})
const labels = reactive<Record<string, string>>({})

const allLevelsFilled = computed(() => {
  return props.action.cascaderLevels?.every(l => selections[l.key]) ?? false
})

function onLevelChange(key: string, val: string, options: { label: string; value: string }[]) {
  selections[key] = val
  const opt = options.find(o => o.value === val)
  labels[key] = opt?.label || val
}

function submit() {
  const result: Record<string, { value: string; label: string }> = {}
  for (const key of Object.keys(selections)) {
    result[key] = { value: selections[key], label: labels[key] || selections[key] }
  }
  emit('resolve', result)
}
</script>

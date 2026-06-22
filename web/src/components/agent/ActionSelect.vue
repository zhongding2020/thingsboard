<template>
  <div class="flex items-center gap-2">
    <el-select
      v-model="selected"
      :placeholder="action.placeholder || '请选择'"
      size="small"
      class="flex-1"
      @change="onChange"
    >
      <el-option
        v-for="opt in action.options"
        :key="opt.value"
        :label="opt.label"
        :value="opt.value"
        :disabled="opt.disabled"
      />
    </el-select>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { InteractiveAction } from '@/composables/useAgentStream'

const props = defineProps<{ action: InteractiveAction }>()
const emit = defineEmits<{ resolve: [value: unknown] }>()

const selected = ref((props.action.defaultValue as string) || '')

function onChange(val: string) {
  const opt = props.action.options?.find(o => o.value === val)
  emit('resolve', { value: val, label: opt?.label || val })
}
</script>

<template>
  <div class="flex items-center gap-2">
    <el-select
      v-model="selected"
      :placeholder="'请选择'"
      size="small"
      class="flex-1"
      @change="onChange"
    >
      <el-option
        v-for="(opt, i) in options || []"
        :key="opt.value || i"
        :label="opt.label"
        :value="opt.value ?? opt.label ?? ''"
        :disabled="opt.disabled"
      />
    </el-select>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  options?: { label: string; value: string; disabled?: boolean }[]
  modelValue?: string
}>()
const emit = defineEmits<{ select: [value: string] }>()

const selected = computed({
  get: () => props.modelValue ?? '',
  set: (val: string) => emit('select', val),
})

function onChange(val: string) {
  emit('select', val)
}
</script>

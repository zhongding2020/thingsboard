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
        v-for="opt in options || []"
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

defineProps<{
  options?: { label: string; value: string; disabled?: boolean }[]
  modelValue?: string
}>()
const emit = defineEmits<{ select: [value: string] }>()

const selected = ref('')

function onChange(val: string) {
  emit('select', val)
}
</script>

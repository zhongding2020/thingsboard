<template>
  <div class="flex flex-col gap-2">
    <el-checkbox-group v-model="checked" size="small" class="flex flex-col gap-1.5">
      <el-checkbox
        v-for="opt in options || []"
        :key="opt.value"
        :value="opt.value"
        :disabled="opt.disabled"
        :label="opt.label"
      />
    </el-checkbox-group>
    <button
      :disabled="!checked.length"
      class="self-start px-3 py-1 text-[11px] rounded-md bg-blue-500 hover:bg-blue-600 disabled:opacity-40 text-white border-none cursor-pointer transition-colors"
      @click="submit"
    >确认选择</button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

defineProps<{
  options?: { label: string; value: string; disabled?: boolean }[]
  modelValue?: string
}>()
const emit = defineEmits<{ select: [values: string[]] }>()

const checked = ref<string[]>([])

function submit() {
  emit('select', checked.value)
}
</script>

<template>
  <div class="flex flex-col gap-2">
    <div v-for="level in levels" :key="level.key" class="flex flex-col gap-1">
      <span class="level-label">{{ level.label }}</span>
      <el-select
        :model-value="selections[level.key]"
        :placeholder="`请选择${level.label}`"
        size="small"
        @change="(val: string) => onLevelChange(level.key, val)"
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
      class="cascader-submit"
      @click="submit"
    >确认选择</button>
  </div>
</template>

<script setup lang="ts">
import { reactive, computed } from 'vue'

defineProps<{
  levels?: { key: string; label: string; options: { label: string; value: string; disabled?: boolean }[] }[]
}>()
const emit = defineEmits<{ complete: [values: Record<string, string>] }>()

const selections = reactive<Record<string, string>>({})
const allLevelsFilled = computed(() => false)  // simplified

function onLevelChange(key: string, val: string) {
  selections[key] = val
}

function submit() {
  emit('complete', { ...selections })
}
</script>

<style scoped>
.level-label { font-size: 11px; color: #9ca3af; }
.cascader-submit { align-self: flex-start; padding: 6px 16px; font-size: 12px; border-radius: 6px; background: #3b82f6; color: #fff; border: none; cursor: pointer; }
.cascader-submit:disabled { opacity: 0.4; cursor: not-allowed; }
</style>

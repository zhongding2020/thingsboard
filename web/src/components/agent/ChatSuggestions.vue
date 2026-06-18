<template>
  <div class="suggestions-bar">
    <div v-for="(q, i) in questions" :key="i" class="suggestion-chip" @click="$emit('select', q)">{{ q }}</div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ questions: string[] }>()
defineEmits<{ select: [q: string] }>()
</script>

<style scoped>
.suggestions-bar { display: flex; flex-wrap: wrap; gap: 8px; padding: 4px 0; align-self: flex-start; }
.suggestion-chip { padding: 6px 12px; border-radius: 14px; font-size: 12px; cursor: pointer; background: linear-gradient(135deg, #667eea22, #764ba222); border: 1px solid var(--el-color-primary-light-7); color: var(--el-color-primary); transition: all 0.2s; white-space: nowrap; max-width: 100%; overflow: hidden; text-overflow: ellipsis; }
.suggestion-chip:hover { background: linear-gradient(135deg, #667eea44, #764ba244); border-color: var(--el-color-primary); transform: translateY(-1px); box-shadow: 0 2px 8px rgba(99,102,241,0.2); }
</style>

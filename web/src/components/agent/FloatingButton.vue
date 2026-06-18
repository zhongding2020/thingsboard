<template>
  <el-button
    class="agent-float" circle
    :style="{ top: y + 'px', bottom: 'auto', right: 'auto', left: x + 'px' }"
    @click="$emit('click')"
    @mousedown.prevent="onMouseDown"
  >
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l2.5 5.5L20 9.5l-4 4 .5 5.5L12 16l-4.5 3 .5-5.5-4-4L9.5 8.5z"/></svg>
  </el-button>
</template>

<script setup lang="ts">
import { useDrag } from '@/composables/useDrag'
defineEmits<{ click: [] }>()
const { x, y, onMouseDown } = useDrag()
</script>

<style scoped>
.agent-float { position: fixed; z-index: 10000; width: 44px; height: 44px; display: flex; align-items: center; justify-content: center; border-radius: 50%; color: #fff; border: none; cursor: grab; background: linear-gradient(135deg, #6366f1, #8b5cf6); box-shadow: 0 4px 20px rgba(99,102,241,0.4); transition: box-shadow 0.2s; }
.agent-float:active { cursor: grabbing; }
.agent-float:hover { box-shadow: 0 6px 24px rgba(99,102,241,0.55); }
</style>

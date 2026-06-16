<template>
  <el-button
    class="agent-float"
    circle
    :style="{ top: floatY + 'px', bottom: 'auto', right: 'auto', left: floatX + 'px' }"
    @click="$router.push('/chat')"
    @mousedown.prevent="startDrag"
  >
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M12 3l2.5 5.5L20 9.5l-4 4 .5 5.5L12 16l-4.5 3 .5-5.5-4-4L9.5 8.5z"/>
    </svg>
  </el-button>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const floatX = ref(window.innerWidth - 64)
const floatY = ref(window.innerHeight / 2 - 22)
let dragging = false
let dragStartX = 0, dragStartY = 0, dragStartFloatX = 0, dragStartFloatY = 0

function startDrag(e: MouseEvent) {
  dragging = true
  dragStartX = e.clientX; dragStartY = e.clientY
  dragStartFloatX = floatX.value; dragStartFloatY = floatY.value
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
}
function onDrag(e: MouseEvent) {
  if (!dragging) return
  floatX.value = Math.max(0, Math.min(window.innerWidth - 44, dragStartFloatX + dragStartX - e.clientX))
  floatY.value = Math.max(0, Math.min(window.innerHeight - 44, dragStartFloatY + e.clientY - dragStartY))
}
function stopDrag() {
  dragging = false
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
}
</script>

<style scoped>
.agent-float {
  position: fixed; z-index: 10000;
  width: 44px; height: 44px; display: flex; align-items: center; justify-content: center;
  border-radius: 50%; color: #fff; border: none; cursor: grab;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  box-shadow: 0 4px 20px rgba(99,102,241,0.4);
  transition: box-shadow 0.2s;
}
.agent-float:active { cursor: grabbing; }
.agent-float:hover { box-shadow: 0 6px 24px rgba(99,102,241,0.55); }
</style>

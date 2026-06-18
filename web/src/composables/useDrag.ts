import { ref } from 'vue'

export function useDrag() {
  const x = ref(window.innerWidth - 64)
  const y = ref(window.innerHeight / 2 - 22)
  let dragging = false, startX = 0, startY = 0, origX = 0, origY = 0

  function onMouseDown(e: MouseEvent) {
    dragging = true
    startX = e.clientX; startY = e.clientY
    origX = x.value; origY = y.value
    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
  }

  function onMouseMove(e: MouseEvent) {
    if (!dragging) return
    x.value = Math.max(0, Math.min(window.innerWidth - 44, origX + startX - e.clientX))
    y.value = Math.max(0, Math.min(window.innerHeight - 44, origY + e.clientY - startY))
  }

  function onMouseUp() {
    dragging = false
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
  }

  return { x, y, onMouseDown }
}

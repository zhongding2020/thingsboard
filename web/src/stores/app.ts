import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const fullscreen = ref(false)

  function toggleFullscreen() {
    fullscreen.value = !fullscreen.value
  }

  function exitFullscreen() {
    fullscreen.value = false
  }

  return { fullscreen, toggleFullscreen, exitFullscreen }
})

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useSessionStore = defineStore('session', () => {
  const currentUser = ref<string | null>(null)
  const role = ref<string | null>(null)
  const isLoggedIn = computed(() => currentUser.value !== null)

  function login(user: string, userRole: string) {
    currentUser.value = user
    role.value = userRole
  }

  function logout() {
    currentUser.value = null
    role.value = null
  }

  return { currentUser, role, isLoggedIn, login, logout }
})

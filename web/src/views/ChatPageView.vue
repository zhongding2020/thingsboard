<template>
  <div class="chat-page">
    <div class="chat-page-header">
      <h2>工艺参数在线分析与调优</h2>
      <button class="theme-btn" @click="toggleTheme" :title="isDark() ? '浅色模式' : '深色模式'">
        <svg v-if="isDark()" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
        <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3a7 7 0 0 0 9.79 9.79z"/></svg>
      </button>
    </div>
    <ChatView processType="injection_molding" />
  </div>
</template>

<script setup lang="ts">
import ChatView from '@/components/agent/ChatView.vue'

function isDark() {
  return document.documentElement.getAttribute('data-theme') !== 'light'
}

function toggleTheme() {
  const dark = !isDark()
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light')
  localStorage.setItem('processopt-theme', dark ? 'dark' : 'light')
}
</script>

<style scoped>
.chat-page { display: flex; flex-direction: column; height: 100vh; background: #fff; }
.chat-page-header { display: flex; align-items: center; justify-content: space-between; padding: 8px 16px; border-bottom: 1px solid #e5e7eb; }
.chat-page-header h2 { font-size: 14px; font-weight: 600; color: #374151; margin: 0; }
.theme-btn { padding: 4px 8px; border: none; border-radius: 6px; background: transparent; color: #6b7280; cursor: pointer; }
.theme-btn:hover { background: #f3f4f6; }
</style>

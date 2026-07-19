<template>
  <div class="chat-page">
    <div class="chat-page-header">
      <div class="header-brand">
        <svg width="20" height="20" viewBox="0 0 48 48" fill="none" class="header-logo">
          <rect x="2" y="2" width="44" height="44" rx="10" stroke="currentColor" stroke-width="2" />
          <path d="M14 30V18M20 30V22M26 30V14M32 30V26M38 30V20" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" />
          <path d="M10 34h28" stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity="0.5" />
        </svg>
        <span class="header-title">工艺参数在线分析与调优</span>
      </div>
      <div class="header-actions">
        <span class="header-model-badge">AI 分析</span>
        <button class="theme-btn" @click="toggleTheme" :title="isDark() ? '浅色模式' : '深色模式'">
          <svg v-if="isDark()" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3a7 7 0 0 0 9.79 9.79z"/></svg>
        </button>
      </div>
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
.chat-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--el-bg-color, #f8fafc);
}

.chat-page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  height: 48px;
  border-bottom: 1px solid var(--el-border-color, #e2e8f0);
  flex-shrink: 0;
  background: var(--el-fill-color, #fff);
}

.header-brand {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-logo {
  color: var(--el-color-primary, #2563eb);
  flex-shrink: 0;
}

.header-title {
  font-family: 'Fira Code', monospace;
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary, #0f172a);
  letter-spacing: -0.3px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-model-badge {
  font-size: 10px;
  font-weight: 500;
  color: var(--el-color-primary, #2563eb);
  background: var(--el-color-primary-light-9, #eff6ff);
  padding: 2px 8px;
  border-radius: 10px;
  letter-spacing: 0.3px;
}

.theme-btn {
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--el-text-color-secondary, #64748b);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.theme-btn:hover {
  background: var(--el-fill-color-light, #f1f5f9);
  color: var(--el-text-color-primary, #0f172a);
}
</style>

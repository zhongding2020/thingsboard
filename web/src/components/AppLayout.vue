<template>
  <el-container class="app-layout">
    <el-aside :width="collapsed ? '64px' : '200px'" class="app-aside" v-show="!app.fullscreen">
      <div class="sidebar-brand">
        <svg width="28" height="28" viewBox="0 0 48 48" fill="none" class="sidebar-logo">
          <rect x="2" y="2" width="44" height="44" rx="10" stroke="currentColor" stroke-width="2" />
          <path d="M14 30V18M20 30V22M26 30V14M32 30V26M38 30V20" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" />
          <path d="M10 34h28" stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity="0.5" />
        </svg>
        <span v-show="!collapsed" class="sidebar-title">ProcessOpt</span>
      </div>
      <el-menu
        :default-active="route.path"
        router
        :collapse="collapsed"
        class="sidebar-menu"
      >
        <el-menu-item index="/dashboard">
          <el-icon><Monitor /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>
        <el-menu-item index="/data">
          <el-icon><DocumentCopy /></el-icon>
          <span>原始数据</span>
        </el-menu-item>
        <el-menu-item index="/lines">
          <el-icon><TrendCharts /></el-icon>
          <span>线体监控</span>
        </el-menu-item>
        <el-menu-item index="/analysis">
          <el-icon><DataAnalysis /></el-icon>
          <span>参数调优</span>
        </el-menu-item>
        <el-menu-item index="/parameters">
          <el-icon><Setting /></el-icon>
          <span>参数管理</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><Tools /></el-icon>
          <span>设置</span>
        </el-menu-item>
      </el-menu>
      <div class="sidebar-user">
        <div class="user-avatar">{{ session.currentUser?.[0]?.toUpperCase() || 'A' }}</div>
        <div v-show="!collapsed" class="user-info">
          <span class="user-name">{{ session.currentUser || '未登录' }}</span>
          <span class="user-role">{{ session.role || '操作员' }}</span>
        </div>
      </div>
    </el-aside>
    <el-container :class="{ 'app-container-fullscreen': app.fullscreen }">
      <el-header class="app-header" v-show="!app.fullscreen">
        <div class="header-left">
          <el-button text @click="collapsed = !collapsed" class="collapse-btn">
            <el-icon size="18"><Fold v-if="!collapsed" /><Expand v-else /></el-icon>
          </el-button>
          <span class="header-title">工艺参数分析与优化平台</span>
        </div>
        <div class="header-actions">
          <span class="header-time">{{ currentTime }}</span>
          <ThemeToggle />
          <el-button text size="small" @click="$router.push('/guide')" class="guide-btn">指南</el-button>
          <el-button text @click="handleLogout">退出登录</el-button>
        </div>
      </el-header>
      <el-main>
        <router-view v-slot="{ Component }">
          <transition name="page-fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Monitor, DocumentCopy, TrendCharts, DataAnalysis, Setting, Tools, Fold, Expand } from '@element-plus/icons-vue'
import { useSessionStore } from '@/stores/session'
import { useAppStore } from '@/stores/app'
import ThemeToggle from '@/components/ThemeToggle.vue'

const route = useRoute()
const router = useRouter()
const session = useSessionStore()
const app = useAppStore()

const collapsed = ref(false)
const currentTime = ref('')
let timer: number | undefined

function updateTime() {
  const now = new Date()
  currentTime.value = now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

onMounted(() => {
  updateTime()
  timer = window.setInterval(updateTime, 30000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

function handleLogout() {
  session.logout()
  router.push('/login')
}
</script>

<style scoped>
.app-layout {
  height: 100vh;
}
.app-layout :deep(.el-main) {
  padding: 12px;
}
.app-container-fullscreen :deep(.el-main) {
  padding: 0 !important;
}

.app-aside {
  transition: width 0.25s ease;
  overflow: hidden;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 14px 10px;
  border-bottom: 1px solid var(--el-border-color);
  white-space: nowrap;
}

.sidebar-logo {
  color: var(--el-color-primary);
  flex-shrink: 0;
}

.sidebar-title {
  font-family: 'Fira Code', monospace;
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  letter-spacing: -0.3px;
}

.sidebar-menu {
  border-right: none;
  padding: 4px 0;
}

.sidebar-menu .el-menu-item {
  margin: 1px 8px;
  border-radius: 6px;
  width: auto;
}
.app-aside :deep(.el-menu--collapse .el-menu-item) {
  margin: 2px 0;
  border-radius: 6px;
  justify-content: center;
  padding: 0;
}

.sidebar-menu .el-menu-item.is-active {
  background: rgba(59, 130, 246, 0.12);
}

.sidebar-user {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 8px;
  border-top: 1px solid var(--el-border-color);
  margin-top: auto;
  white-space: nowrap;
}

.user-avatar {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: var(--el-color-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  font-family: 'Fira Code', monospace;
  flex-shrink: 0;
}

.user-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.user-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-role {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--el-fill-color);
  border-bottom: 1px solid var(--el-border-color);
  padding: 0 16px;
  height: 44px !important;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.collapse-btn {
  color: var(--el-text-color-secondary);
  padding: 4px;
}
.collapse-btn:hover {
  color: var(--el-text-color-primary);
}

.header-title {
  font-size: 12px;
  font-weight: 500;
  color: var(--el-text-color-secondary);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-time {
  font-family: 'Fira Code', monospace;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.guide-btn {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.page-fade-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.page-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>

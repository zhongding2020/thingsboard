<template>
  <div class="login-container">
    <div class="login-bg">
      <div class="grid-overlay" />
      <div class="glow-spot glow-spot-1" />
      <div class="glow-spot glow-spot-2" />
    </div>
    <div class="login-card">
      <div class="login-brand">
        <div class="brand-icon">
          <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
            <rect x="2" y="2" width="44" height="44" rx="10" stroke="currentColor" stroke-width="2" />
            <path d="M14 30V18M20 30V22M26 30V14M32 30V26M38 30V20" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" />
            <path d="M10 34h28" stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity="0.5" />
          </svg>
        </div>
        <h1 class="brand-title">ProcessOpt</h1>
        <p class="brand-subtitle">工艺参数分析与优化平台</p>
      </div>
      <el-form class="login-form" @submit.prevent="handleLogin">
        <el-form-item>
          <el-input v-model="username" placeholder="用户名" size="large" :prefix-icon="User" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="password" type="password" placeholder="密码" size="large" :prefix-icon="Lock" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" native-type="submit" :loading="loading" size="large" class="login-btn">
            登录系统
          </el-button>
        </el-form-item>
      </el-form>
      <p class="login-footer">ProcessOpt v1.0 · 工业参数优化平台</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/stores/session'
import { User, Lock } from '@element-plus/icons-vue'

const router = useRouter()
const session = useSessionStore()

const username = ref('')
const password = ref('')
const loading = ref(false)

function handleLogin() {
  loading.value = true
  setTimeout(() => {
    session.login(username.value || 'admin', 'admin')
    router.push('/dashboard')
    loading.value = false
  }, 500)
}
</script>

<style scoped>
.login-container {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: var(--el-bg-color);
  overflow: hidden;
}

.login-bg {
  position: absolute;
  inset: 0;
}

.grid-overlay {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(59, 130, 246, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(59, 130, 246, 0.04) 1px, transparent 1px);
  background-size: 48px 48px;
}

.glow-spot {
  position: absolute;
  width: 400px;
  height: 400px;
  border-radius: 50%;
  filter: blur(100px);
  opacity: 0.15;
}

.glow-spot-1 {
  top: -100px;
  right: -100px;
  background: #3B82F6;
}

.glow-spot-2 {
  bottom: -100px;
  left: -100px;
  background: #059669;
}

.login-card {
  position: relative;
  width: 380px;
  padding: 40px;
  background: var(--el-fill-color);
  border: 1px solid var(--el-border-color);
  border-radius: 12px;
  animation: cardIn 0.6s ease-out;
}

@keyframes cardIn {
  from {
    opacity: 0;
    transform: translateY(20px) scale(0.97);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.login-brand {
  text-align: center;
  margin-bottom: 32px;
}

.brand-icon {
  color: #3B82F6;
  margin-bottom: 16px;
}

.brand-title {
  font-family: 'Fira Code', monospace;
  font-size: 28px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0 0 8px;
  letter-spacing: -0.5px;
}

.brand-subtitle {
  font-family: 'Fira Sans', sans-serif;
  font-size: 14px;
  color: var(--el-text-color-secondary);
  margin: 0;
}

.login-form {
  margin-bottom: 24px;
}

.login-form :deep(.el-input__wrapper) {
  background: var(--el-fill-color-light);
  box-shadow: 0 0 0 1px var(--el-border-color) inset;
}

.login-form :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px #3B82F6 inset;
}

.login-form :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px #3B82F6 inset, 0 0 0 3px rgba(59, 130, 246, 0.15);
}

.login-form :deep(.el-input__inner) {
  color: var(--el-text-color-primary);
}

.login-form :deep(.el-input__inner::placeholder) {
  color: var(--el-text-color-placeholder);
}

.login-btn {
  width: 100%;
  height: 44px;
  font-size: 15px;
  font-weight: 500;
  letter-spacing: 1px;
}

.login-footer {
  text-align: center;
  font-size: 12px;
  color: var(--el-text-color-disabled);
  margin: 0;
}
</style>

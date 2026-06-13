import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '@/components/AppLayout.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      component: () => import('@/views/LoginView.vue'),
    },
    {
      path: '/',
      component: AppLayout,
      redirect: '/dashboard',
      children: [
        { path: 'dashboard', component: () => import('@/views/DashboardView.vue') },
        { path: 'data', component: () => import('@/views/DataView.vue') },
        { path: 'spc', component: () => import('@/views/SpcView.vue') },
        { path: 'guide', component: () => import('@/views/GuideView.vue') },
        { path: 'analysis', component: () => import('@/views/AnalysisView.vue') },
        { path: 'parameters', component: () => import('@/views/ParametersView.vue') },
        { path: 'settings', component: () => import('@/views/SettingsView.vue') },
      ],
    },
  ],
})

export default router

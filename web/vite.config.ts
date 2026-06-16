import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import opencodeAssistant from 'vite-plugin-opencode-assistant'

export default defineConfig({
  plugins: [
    vue(),
    opencodeAssistant({
      language: 'zh',
      theme: 'auto',
      hotkey: 'ctrl+k',
      open: false,
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})

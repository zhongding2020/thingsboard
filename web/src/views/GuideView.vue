<template>
  <div class="guide-view">
    <div class="guide-header">
      <h2 class="page-title">操作指南</h2>
      <p class="page-desc">平台使用说明与设备接入文档</p>
    </div>

    <el-tabs v-model="activeTab" class="guide-tabs">
      <el-tab-pane label="平台操作说明" name="operation">
        <div v-if="operationHtml" class="markdown-body" v-html="operationHtml" />
        <el-skeleton v-else :rows="8" animated />
      </el-tab-pane>
      <el-tab-pane label="设备接口文档" name="api">
        <div v-if="apiHtml" class="markdown-body" v-html="apiHtml" />
        <el-skeleton v-else :rows="8" animated />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { marked } from 'marked'

const activeTab = ref('operation')
const operationHtml = ref('')
const apiHtml = ref('')

async function loadMd(path: string): Promise<string> {
  const res = await fetch(path)
  const text = await res.text()
  return marked.parse(text) as string
}

onMounted(async () => {
  try {
    const [op, api] = await Promise.all([
      loadMd('/docs/operation.md'),
      loadMd('/docs/api.md'),
    ])
    operationHtml.value = op
    apiHtml.value = api
  } catch {
    // silently fail
  }
})
</script>

<style scoped>
.guide-view {
  padding-bottom: 40px;
}
.guide-header {
  margin-bottom: 12px;
}
.page-title {
  font-family: 'Fira Code', monospace;
  font-size: 20px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0 0 2px;
}
.page-desc {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin: 0;
}
.guide-tabs {
  margin-top: 12px;
}
</style>

<style>
.markdown-body {
  max-width: 800px;
  font-size: 14px;
  line-height: 1.8;
  color: var(--el-text-color-regular);
}
.markdown-body h2 {
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 24px 0 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--el-border-color);
}
.markdown-body h4 {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-color-primary);
  margin: 12px 0 6px;
}
.markdown-body p {
  margin: 6px 0;
}
.markdown-body ul {
  padding-left: 20px;
  margin: 6px 0;
}
.markdown-body li {
  margin: 3px 0;
}
.markdown-body strong {
  color: var(--el-text-color-primary);
}
.markdown-body code {
  font-family: 'Fira Code', monospace;
  font-size: 12px;
  background: var(--el-fill-color-light);
  padding: 2px 6px;
  border-radius: 4px;
  color: var(--el-color-primary);
}
.markdown-body pre {
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  padding: 12px 14px;
  overflow-x: auto;
  margin: 10px 0;
}
.markdown-body pre code {
  background: none;
  padding: 0;
  color: var(--el-text-color-primary);
  font-size: 12px;
  line-height: 1.6;
}
.markdown-body table {
  width: 100%;
  border-collapse: collapse;
  margin: 10px 0;
  font-size: 13px;
}
.markdown-body th,
.markdown-body td {
  border: 1px solid var(--el-border-color);
  padding: 6px 10px;
  text-align: left;
}
.markdown-body th {
  background: var(--el-fill-color-light);
  font-weight: 500;
  color: var(--el-text-color-secondary);
}
.markdown-body hr {
  border: none;
  border-top: 1px solid var(--el-border-color-light);
  margin: 16px 0;
}
</style>

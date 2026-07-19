<template>
  <div class="text-part markdown-body">
    <div v-html="rendered" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'

const props = defineProps<{ text: string }>()

const rendered = computed(() => {
  const html = marked.parse(props.text || '', { breaks: true })
  return typeof html === 'string' ? html : ''
})
</script>

<style scoped>
.text-part {
  line-height: 1.7;
  color: var(--el-text-color-primary, #0f172a);
}

.text-part :deep(p) {
  margin: 0.4em 0;
}

.text-part :deep(code) {
  background: var(--el-fill-color-light, #f1f5f9);
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 0.88em;
  font-family: 'Fira Code', monospace;
  color: var(--el-text-color-regular, #334155);
}

.text-part :deep(pre) {
  background: var(--el-fill-color-light, #f1f5f9);
  border: 1px solid var(--el-border-color, #e2e8f0);
  border-radius: 8px;
  padding: 12px 14px;
  overflow-x: auto;
  margin: 0.5em 0;
}

.text-part :deep(pre code) {
  background: none;
  padding: 0;
  font-size: 13px;
  line-height: 1.5;
}

.text-part :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 0.5em 0;
  font-size: 13px;
}

.text-part :deep(th),
.text-part :deep(td) {
  border: 1px solid var(--el-border-color, #e2e8f0);
  padding: 6px 10px;
  text-align: left;
}

.text-part :deep(th) {
  background: var(--el-fill-color-lighter, #f8fafc);
  font-weight: 600;
  font-size: 12px;
  color: var(--el-text-color-secondary, #64748b);
}

.text-part :deep(hr) {
  border: none;
  border-top: 1px solid var(--el-border-color, #e2e8f0);
  margin: 1em 0;
}

.text-part :deep(ul),
.text-part :deep(ol) {
  padding-left: 1.5em;
}

.text-part :deep(li) {
  margin: 0.2em 0;
}

.text-part :deep(blockquote) {
  border-left: 3px solid var(--el-border-color-dark, #cbd5e1);
  padding-left: 0.8em;
  color: var(--el-text-color-secondary, #64748b);
  margin: 0.5em 0;
}

.text-part :deep(a) {
  color: var(--el-color-primary, #2563eb);
  text-decoration: none;
}

.text-part :deep(a:hover) {
  text-decoration: underline;
}

.text-part :deep(h1),
.text-part :deep(h2),
.text-part :deep(h3),
.text-part :deep(h4) {
  margin: 0.6em 0 0.3em;
  color: var(--el-text-color-primary, #0f172a);
  font-weight: 600;
  line-height: 1.4;
}

.text-part :deep(h1) { font-size: 1.3em; }
.text-part :deep(h2) { font-size: 1.15em; }
.text-part :deep(h3) { font-size: 1.05em; }
.text-part :deep(h4) { font-size: 1em; }

.text-part :deep(strong) {
  font-weight: 600;
}

.text-part :deep(img) {
  max-width: 100%;
  border-radius: 8px;
  margin: 0.5em 0;
}
</style>

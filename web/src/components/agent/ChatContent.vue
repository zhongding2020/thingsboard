<template>
  <div class="chat-content" v-html="rendered"></div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import mermaid from 'mermaid'
import * as echarts from 'echarts'

mermaid.initialize({ startOnLoad: false, theme: 'default' })

const props = defineProps<{ text: string; uid: string }>()

function findEchartsJson(text: string): string[] {
  const results: string[] = []
  let i = 0
  while (i < text.length) {
    i = text.indexOf('"xAxis"', i)
    if (i === -1) break
    const start = text.lastIndexOf('{', i - 20)
    if (start === -1 || start < i - 100) { i += 6; continue }
    let depth = 0, end = -1
    for (let j = start; j < text.length; j++) {
      if (text[j] === '{') depth++
      else if (text[j] === '}') { depth--; if (depth === 0) { end = j + 1; break } }
    }
    if (end > 0) {
      try {
        const candidate = text.slice(start, end)
        const parsed = JSON.parse(candidate)
        if (parsed.series && (parsed.xAxis || parsed.yAxis)) {
          results.push(candidate)
          i = end
          continue
        }
      } catch {}
    }
    i += 6
  }
  return results
}

const rendered = computed(() => {
  let processed = props.text
  const jsonPatterns = findEchartsJson(props.text)
  for (const json of jsonPatterns) {
    processed = processed.replace(json, '\n```echarts\n' + json + '\n```\n')
  }

  let html = marked.parse(processed, { breaks: true, gfm: true }) as string

  html = html.replace(/<pre><code class="language-echarts">([\s\S]*?)<\/code><\/pre>/g, (_, code) => {
    const id = 'echarts-' + props.uid + '-' + Math.random().toString(36).slice(2, 6)
    setTimeout(() => {
      try {
        const option = JSON.parse(code.trim())
        const el = document.getElementById(id)
        if (!el) return
        const chart = echarts.init(el)
        chart.setOption(option)
        new ResizeObserver(() => chart.resize()).observe(el)
      } catch {}
    }, 50)
    return `<div class="echarts-block" id="${id}" style="width:100%;height:360px"><div class="echarts-loading">渲染图表中...</div></div>`
  })

  html = html.replace(/<pre><code class="language-json">([\s\S]*?)<\/code><\/pre>/g, (_, code) => {
    try {
      const parsed = JSON.parse(code.trim())
      if (parsed.series && (parsed.xAxis || parsed.yAxis)) {
        const id = 'echarts-' + props.uid + '-' + Math.random().toString(36).slice(2, 6)
        setTimeout(() => {
          try {
            const option = JSON.parse(code.trim())
            const el = document.getElementById(id)
            if (!el) return
            const chart = echarts.init(el)
            chart.setOption(option)
            new ResizeObserver(() => chart.resize()).observe(el)
          } catch {}
        }, 50)
        return `<div class="echarts-block" id="${id}" style="width:100%;height:360px"><div class="echarts-loading">渲染图表中...</div></div>`
      }
    } catch {}
    return _
  })

  html = html.replace(/<pre><code class="language-mermaid">([\s\S]*?)<\/code><\/pre>/g, (_, code) => {
    const id = 'mermaid-' + props.uid + '-' + Math.random().toString(36).slice(2, 6)
    setTimeout(() => {
      mermaid.render(id + '-svg', code.trim()).then(({ svg }) => {
        const el = document.getElementById(id)
        if (el) el.innerHTML = svg
      }).catch(() => {
        const el = document.getElementById(id)
        if (el) el.innerHTML = '<pre style="color:red;font-size:12px">图表语法错误</pre>'
      })
    }, 50)
    return `<div class="mermaid-block" id="${id}"><div class="mermaid-loading">渲染图表中...</div></div>`
  })

  return html
})
</script>

<style scoped>
.chat-content :deep(p) { margin: 0 0 8px; }
.chat-content :deep(p:last-child) { margin-bottom: 0; }
.chat-content :deep(code) { background: var(--el-fill-color-dark); padding: 2px 5px; border-radius: 4px; font-size: 12px; }
.chat-content :deep(pre) { background: var(--el-fill-color); padding: 10px; border-radius: 8px; overflow-x: auto; font-size: 12px; }
.chat-content :deep(table) { border-collapse: collapse; width: 100%; font-size: 12px; }
.chat-content :deep(th), .chat-content :deep(td) { border: 1px solid var(--el-border-color-light); padding: 4px 8px; }
.chat-content :deep(th) { background: var(--el-fill-color); }
.chat-content :deep(blockquote) { border-left: 3px solid var(--el-color-primary); padding-left: 10px; color: var(--el-text-color-secondary); }
.mermaid-block { margin: 8px 0; padding: 12px; background: #fff; border-radius: 8px; border: 1px solid var(--el-border-color-light); overflow-x: auto; }
.mermaid-block svg { max-width: 100%; height: auto; }
.mermaid-loading, .echarts-loading { font-size: 12px; color: var(--el-text-color-placeholder); padding: 20px; text-align: center; }
.echarts-block { margin: 8px 0; border-radius: 8px; border: 1px solid var(--el-border-color-light); }
</style>

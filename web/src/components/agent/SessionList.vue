<template>
  <div class="sessions-view">
    <div class="sessions-title">历史会话 ({{ sessions.length }})</div>
    <div v-for="s in sessions" :key="s.id" class="session-card" :class="{ active: s.id === activeId }" @click="$emit('select', s.id)">
      <div class="session-card-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg></div>
      <div class="session-card-text"><div class="session-card-name">{{ s.title || '会话 ' + s.id.slice(0, 8) }}</div></div>
      <el-button link size="small" class="session-delete" @click.stop="$emit('delete', s.id)">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
      </el-button>
    </div>
    <div v-if="!sessions.length" class="sessions-empty">暂无历史会话</div>
  </div>
</template>

<script setup lang="ts">
interface SessionItem { id: string; title?: string }
defineProps<{ sessions: SessionItem[]; activeId: string }>()
defineEmits<{ select: [id: string]; delete: [id: string] }>()
</script>

<style scoped>
.sessions-view { padding: 4px 0; }
.sessions-title { font-size: 13px; font-weight: 600; padding: 0 0 10px; color: var(--el-text-color-primary); }
.session-card { display: flex; align-items: center; gap: 8px; padding: 8px 10px; border-radius: 8px; cursor: pointer; font-size: 13px; }
.session-card:hover { background: var(--el-fill-color); }
.session-card.active { background: var(--el-color-primary-light-8); color: var(--el-color-primary); }
.session-card-icon { flex-shrink: 0; color: var(--el-text-color-secondary); }
.session-card.active .session-card-icon { color: var(--el-color-primary); }
.session-card-text { flex: 1; overflow: hidden; }
.session-card-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.session-delete { opacity: 0; flex-shrink: 0; }
.session-card:hover .session-delete { opacity: 1; }
.sessions-empty { font-size: 12px; color: var(--el-text-color-secondary); padding: 30px 0; text-align: center; }
</style>

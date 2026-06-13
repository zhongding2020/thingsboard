<template>
  <div class="data-preview">
    <div class="preview-summary">
      <span>共 {{ total }} 条数据 · {{ props.fields.features.length }} 参数 / {{ props.fields.targets.length }} 结果</span>
      <el-pagination
        v-if="total > size"
        small
        layout="prev, pager, next"
        :total="total"
        :page-size="size"
        :current-page="page"
        @current-change="$emit('page-change', $event)"
      />
    </div>
    <el-table :data="rows" stripe size="small" v-loading="loading" max-height="420" empty-text="暂无数据">
      <el-table-column
        v-for="f in props.fields.features" :key="f.name" :label="f.name" :prop="f.name" min-width="130"
      >
        <template #header>
          <span class="feature-header">{{ f.name }}</span>
        </template>
        <template #default="{ row }">
          <span class="cell-mono">{{ row[f.name] !== null && row[f.name] !== undefined ? Number(row[f.name]).toFixed(2) : '—' }}</span>
        </template>
      </el-table-column>
      <el-table-column
        v-for="t in props.fields.targets" :key="t.name" :label="t.name" :prop="t.name" min-width="140"
      >
        <template #header>
          <span class="target-header">{{ t.name }}</span>
        </template>
        <template #default="{ row }">
          <el-tag v-if="row[t.name] === 'pass'" size="small" type="success">pass</el-tag>
          <el-tag v-else-if="row[t.name] === 'fail'" size="small" type="danger">fail</el-tag>
          <span v-else class="cell-mono">{{ row[t.name] ?? '—' }}</span>
        </template>
      </el-table-column>
    </el-table>
    <div class="preview-footer">
      <el-button type="primary" @click="$emit('confirm')">确认数据，前往配置 →</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { FieldMeta } from '@/api/analysis'

const props = defineProps<{
  rows: Record<string, unknown>[]
  total: number
  size: number
  page: number
  fields: { features: FieldMeta[]; targets: FieldMeta[] }
  loading?: boolean
}>()

defineEmits<{
  'page-change': [page: number]
  confirm: []
}>()
</script>

<style scoped>
.data-preview {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.preview-summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.feature-header {
  color: var(--el-color-primary);
  font-weight: 600;
  font-family: 'Fira Code', monospace;
  font-size: 12px;
}
.target-header {
  color: #a855f7;
  font-weight: 600;
  font-family: 'Fira Code', monospace;
  font-size: 12px;
}
.cell-mono {
  font-family: 'Fira Code', monospace;
  font-size: 12px;
}
.preview-footer {
  display: flex;
  justify-content: flex-end;
}
</style>

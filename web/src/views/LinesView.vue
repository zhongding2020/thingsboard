<template>
  <div class="lines-view">
    <div class="page-header">
      <div>
        <h2 class="page-title">线体监控</h2>
        <p class="page-desc">生产线管理 & 设备聚合监控</p>
      </div>
      <el-button type="primary" @click="openCreate">+ 新建线体</el-button>
    </div>

    <el-card class="lines-table-card">
      <el-table :data="lines" stripe size="small" v-loading="loading" empty-text="暂无产线，点击上方按钮创建">
        <el-table-column prop="name" label="线体名称" min-width="140" class-name="cell-mono">
          <template #default="{ row }">
            <router-link :to="`/lines/${row.id}`" class="line-link">{{ row.name }}</router-link>
          </template>
        </el-table-column>
        <el-table-column prop="responsible" label="责任人" width="100" class-name="cell-mono" />
        <el-table-column prop="location" label="位置" width="120" class-name="cell-mono">
          <template #default="{ row }">{{ row.location || '—' }}</template>
        </el-table-column>
        <el-table-column prop="device_count" label="设备数" width="80" class-name="cell-mono" />
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button text size="small" @click="openEdit(row)">编辑</el-button>
            <el-button text size="small" type="danger" @click="handleDelete(row)" :disabled="row.device_count > 0">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑线体' : '新建线体'" width="480px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="线体名称">
          <el-input v-model="form.name" placeholder="如 SMT-01" />
        </el-form-item>
        <el-form-item label="责任人">
          <el-input v-model="form.responsible" placeholder="负责人姓名" />
        </el-form-item>
        <el-form-item label="位置">
          <el-input v-model="form.location" placeholder="如 A栋2层" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">{{ editing ? '保存' : '创建' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { listLines, createLine, updateLine, deleteLine, type LineResponse } from '@/api/lines'

const lines = ref<LineResponse[]>([])
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editing = ref<LineResponse | null>(null)
const form = ref({ name: '', responsible: '', location: '' })

async function loadLines() {
  loading.value = true
  try { lines.value = await listLines() } finally { loading.value = false }
}

function openCreate() {
  editing.value = null
  form.value = { name: '', responsible: '', location: '' }
  dialogVisible.value = true
}

function openEdit(row: LineResponse) {
  editing.value = row
  form.value = { name: row.name, responsible: row.responsible, location: row.location || '' }
  dialogVisible.value = true
}

async function handleSave() {
  saving.value = true
  try {
    if (editing.value) {
      await updateLine(editing.value.id, form.value)
    } else {
      await createLine(form.value)
    }
    dialogVisible.value = false
    await loadLines()
  } finally { saving.value = false }
}

async function handleDelete(row: LineResponse) {
  await deleteLine(row.id)
  await loadLines()
}

onMounted(loadLines)
</script>

<style scoped>
.lines-view { display: flex; flex-direction: column; gap: 12px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; }
.page-title { font-family: 'Fira Code', monospace; font-size: 20px; font-weight: 600; margin: 0; }
.page-desc { font-size: 13px; color: var(--el-text-color-secondary); margin: 2px 0 0; }
.line-link { color: var(--el-color-primary); text-decoration: none; font-family: 'Fira Code', monospace; }
.line-link:hover { text-decoration: underline; }
</style>

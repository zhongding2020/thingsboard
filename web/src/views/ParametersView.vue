<template>
  <div class="parameters">
    <div class="page-header">
      <div>
        <h2 class="page-title">参数管理</h2>
        <p class="page-desc">工艺参数集版本管理与审批流转</p>
      </div>
      <el-button type="primary" size="small" @click="fetchData" :loading="loading">刷新</el-button>
    </div>
    <el-table
      :data="tableData"
      height="100%"
      stripe
      size="small"
      :default-sort="{ prop: 'id', order: 'ascending' }"
      v-loading="loading"
    >
      <el-table-column prop="id" label="ID" width="60" sortable />
      <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip />
      <el-table-column prop="device_type" label="设备类型" width="100" show-overflow-tooltip />
      <el-table-column prop="version" label="版本" width="60" sortable />
      <el-table-column prop="created_by" label="创建人" width="80" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <ParameterStatus :status="row.status" />
        </template>
      </el-table-column>
      <el-table-column label="更新时间" width="150" class-name="cell-mono" sortable prop="updated_at">
        <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="340">
        <template #default="{ row }">
          <el-button size="small" @click="handleSubmit(row)" :disabled="row.status !== 'draft'">提交</el-button>
          <el-button size="small" type="success" @click="handleApprove(row)" :disabled="row.status !== 'proposed'">批准</el-button>
          <el-button size="small" type="danger" @click="handleReject(row)" :disabled="row.status !== 'proposed'">驳回</el-button>
          <el-button size="small" type="primary" @click="handleActivate(row)" :disabled="row.status !== 'approved'">激活</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div class="pagination-wrapper">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.page_size"
        :page-sizes="[10, 20, 50]"
        :total="total"
        layout="total, sizes, prev, pager, next"
        @current-change="handlePageChange"
        @size-change="handlePageChange"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { listSets, submitSet, approveSet, rejectSet, activateSet, type ParameterSet } from '@/api/parameters'
import { useSessionStore } from '@/stores/session'
import ParameterStatus from '@/components/ParameterStatus.vue'

const session = useSessionStore()

const loading = ref(false)
const allData = ref<ParameterSet[]>([])

const pagination = reactive({
  page: 1,
  page_size: 10,
})

const total = computed(() => allData.value.length)

const tableData = computed(() => {
  const start = (pagination.page - 1) * pagination.page_size
  return allData.value.slice(start, start + pagination.page_size)
})

function formatTime(iso: string) {
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

async function fetchData() {
  loading.value = true
  try {
    allData.value = await listSets()
  } finally {
    loading.value = false
  }
}

function handlePageChange() {
  // computed auto-updates
}

async function handleSubmit(row: ParameterSet) {
  loading.value = true
  try {
    await submitSet(row.id, { actor: session.currentUser || 'operator' })
    await fetchData()
  } finally {
    loading.value = false
  }
}

async function handleApprove(row: ParameterSet) {
  loading.value = true
  try {
    await approveSet(row.id, { actor: session.currentUser || 'operator' })
    await fetchData()
  } finally {
    loading.value = false
  }
}

async function handleReject(row: ParameterSet) {
  loading.value = true
  try {
    await rejectSet(row.id, { actor: session.currentUser || 'operator' })
    await fetchData()
  } finally {
    loading.value = false
  }
}

async function handleActivate(row: ParameterSet) {
  loading.value = true
  try {
    await activateSet(row.id, { actor: session.currentUser || 'operator' })
    await fetchData()
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)
</script>

<style scoped>
.parameters {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}
.page-title {
  font-family: 'Fira Code', monospace;
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 2px;
}
.page-desc {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin: 0;
}
.parameters :deep(.el-table) {
  flex: 1;
  min-height: 0;
}
.parameters :deep(.el-table__body-wrapper) {
  overflow-y: auto;
}
.pagination-wrapper {
  flex-shrink: 0;
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}
</style>
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
      <el-table-column label="操作" width="420">
        <template #default="{ row }">
          <el-button size="small" @click="handleDetail(row)">详情</el-button>
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

    <!-- Detail dialog -->
    <el-dialog v-model="detailVisible" title="参数集详情" width="640px" :close-on-click-modal="false">
      <template v-if="detailData">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="名称" span="2">{{ detailData.parameter_set.name }}</el-descriptions-item>
          <el-descriptions-item label="设备类型">{{ detailData.parameter_set.device_type }}</el-descriptions-item>
          <el-descriptions-item label="版本">{{ detailData.parameter_set.version }}</el-descriptions-item>
          <el-descriptions-item label="来源">{{ detailData.parameter_set.source }}</el-descriptions-item>
          <el-descriptions-item label="创建人">{{ detailData.parameter_set.created_by }}</el-descriptions-item>
          <el-descriptions-item label="状态" span="2">
            <ParameterStatus :status="detailData.parameter_set.status" />
          </el-descriptions-item>
          <el-descriptions-item label="备注" span="2">{{ detailData.parameter_set.note || '—' }}</el-descriptions-item>
          <el-descriptions-item label="校验和">
            <code class="checksum">{{ detailData.checksum }}</code>
          </el-descriptions-item>
          <el-descriptions-item label="参数项数">{{ detailData.items.length }}</el-descriptions-item>
        </el-descriptions>

        <h4 class="items-title">参数项</h4>
        <el-table :data="detailData.items" stripe size="small" max-height="300">
          <el-table-column prop="param_key" label="参数名" min-width="120" />
          <el-table-column label="值" width="100">
            <template #default="{ row }">{{ formatValue(row.param_value, row.data_type) }}</template>
          </el-table-column>
          <el-table-column prop="unit" label="单位" width="60" />
          <el-table-column prop="data_type" label="类型" width="70" />
          <el-table-column label="规格下限" width="90" class-name="cell-mono">
            <template #default="{ row }">{{ row.min_value ?? '—' }}</template>
          </el-table-column>
          <el-table-column label="规格上限" width="90" class-name="cell-mono">
            <template #default="{ row }">{{ row.max_value ?? '—' }}</template>
          </el-table-column>
          <el-table-column prop="description" label="说明" min-width="120" show-overflow-tooltip />
        </el-table>
      </template>
      <div v-else class="detail-loading" v-loading="detailLoading" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { listSets, getSet, submitSet, approveSet, rejectSet, activateSet, type ParameterSet, type ParameterSetWithItems } from '@/api/parameters'
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

function formatValue(value: unknown, dataType: string): string {
  if (value === null || value === undefined) return '—'
  if (dataType === 'float' || dataType === 'double') {
    const n = Number(value)
    return isNaN(n) ? String(value) : n.toFixed(4)
  }
  return String(value)
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

// Detail dialog
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailData = ref<ParameterSetWithItems | null>(null)

async function handleDetail(row: ParameterSet) {
  detailVisible.value = true
  detailLoading.value = true
  detailData.value = null
  try {
    detailData.value = await getSet(row.id)
  } finally {
    detailLoading.value = false
  }
}

// State transitions
async function handleSubmit(row: ParameterSet) {
  loading.value = true
  try {
    await submitSet(row.id, { actor: session.currentUser || 'operator' })
    await fetchData()
  } catch { loading.value = false }
}

async function handleApprove(row: ParameterSet) {
  loading.value = true
  try {
    await approveSet(row.id, { actor: session.currentUser || 'operator' })
    await fetchData()
  } catch { loading.value = false }
}

async function handleReject(row: ParameterSet) {
  loading.value = true
  try {
    await rejectSet(row.id, { actor: session.currentUser || 'operator' })
    await fetchData()
  } catch { loading.value = false }
}

async function handleActivate(row: ParameterSet) {
  loading.value = true
  try {
    await activateSet(row.id, { actor: session.currentUser || 'operator' })
    await fetchData()
  } catch { loading.value = false }
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

.items-title {
  font-size: 14px;
  font-weight: 600;
  margin: 16px 0 8px;
}
.checksum {
  font-family: 'Fira Code', monospace;
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
.detail-loading {
  min-height: 120px;
}
</style>
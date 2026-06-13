<template>
  <div class="parameters">
    <el-table
      :data="tableData"
      height="100%"
      stripe
      size="small"
      :default-sort="{ prop: 'id', order: 'ascending' }"
    >
      <el-table-column prop="id" label="ID" width="70" sortable />
      <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip />
      <el-table-column prop="version" label="版本" width="70" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <ParameterStatus :status="row.status" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="280">
        <template #default="{ row }">
          <el-button size="small" @click="handleSubmit(row)">提交</el-button>
          <el-button size="small" type="success" @click="handleApprove(row)">批准</el-button>
          <el-button size="small" type="danger" @click="handleReject(row)">驳回</el-button>
          <el-button size="small" type="primary" @click="handleActivate(row)">激活</el-button>
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
import { ref, reactive, computed } from 'vue'
import ParameterStatus from '@/components/ParameterStatus.vue'

interface ParamSet {
  id: string
  name: string
  version: string
  status: string
}

const allData = ref<ParamSet[]>([
  { id: '1', name: '温度阈值集', version: 'v1', status: 'approved' },
  { id: '2', name: '湿度参数集', version: 'v2', status: 'proposed' },
  { id: '3', name: '压力参数集', version: 'v3', status: 'active' },
  { id: '4', name: '流量参数集', version: 'v1', status: 'rejected' },
  { id: '5', name: '振动参数集', version: 'v2', status: 'draft' },
  { id: '6', name: '温度阈值集 v2', version: 'v2', status: 'approved' },
  { id: '7', name: '湿度参数集 v3', version: 'v3', status: 'proposed' },
  { id: '8', name: '压力参数集 v2', version: 'v2', status: 'active' },
  { id: '9', name: '流量参数集 v2', version: 'v2', status: 'draft' },
  { id: '10', name: '振动参数集 v2', version: 'v2', status: 'rejected' },
  { id: '11', name: '温度阈值集 v3', version: 'v3', status: 'active' },
  { id: '12', name: '湿度参数集 v4', version: 'v4', status: 'draft' },
])

const pagination = reactive({
  page: 1,
  page_size: 10,
})

const total = computed(() => allData.value.length)

const tableData = computed(() => {
  const start = (pagination.page - 1) * pagination.page_size
  return allData.value.slice(start, start + pagination.page_size)
})

function handlePageChange() {
  // pagination reactive, tableData recomputes automatically
}

function handleSubmit(row: ParamSet) {
  console.log('submit', row.id)
}
function handleApprove(row: ParamSet) {
  console.log('approve', row.id)
}
function handleReject(row: ParamSet) {
  console.log('reject', row.id)
}
function handleActivate(row: ParamSet) {
  console.log('activate', row.id)
}
</script>

<style scoped>
.parameters {
  height: 100%;
  display: flex;
  flex-direction: column;
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

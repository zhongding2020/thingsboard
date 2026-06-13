<template>
  <div class="data-view">
    <el-card class="filter-card">
      <el-form :inline="true" :model="filters" size="default">
        <el-form-item label="条码">
          <el-input v-model="filters.barcode" placeholder="精确条码" clearable />
        </el-form-item>
        <el-form-item label="设备">
          <el-select v-model="filters.device_id" placeholder="全部设备" clearable>
            <el-option
              v-for="d in devices"
              :key="d"
              :label="d"
              :value="d"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="处理时间">
          <el-date-picker
            v-model="timeRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            :shortcuts="timeShortcuts"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="table-card">
      <el-table
        :data="records"
        v-loading="loading"
        style="width: 100%"
        height="100%"
        stripe
        size="small"
        :default-expand-all="false"
      >
        <el-table-column type="expand" width="40">
          <template #default="{ row }">
            <div class="detail-panel">
              <el-descriptions title="工艺参数" :column="1" border size="small">
                <el-descriptions-item
                  v-for="(val, key) in row.params"
                  :key="key"
                  :label="key"
                >
                  {{ val }}
                </el-descriptions-item>
              </el-descriptions>
              <el-descriptions
                v-if="row.results"
                title="检测结果"
                :column="1"
                border
                size="small"
                class="results-desc"
              >
                <el-descriptions-item
                  v-for="(val, key) in row.results"
                  :key="key"
                  :label="key"
                >
                  <el-tag
                    :type="val === 'pass' ? 'success' : 'danger'"
                    size="small"
                  >
                    {{ val }}
                  </el-tag>
                </el-descriptions-item>
              </el-descriptions>
              <el-empty v-else description="暂无检测数据" />
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="barcode" label="条码" min-width="200" show-overflow-tooltip class-name="cell-mono" />
        <el-table-column prop="device_id" label="设备" width="120" />
        <el-table-column prop="inspected_at" label="检测时间" width="160" class-name="cell-mono" />
        <el-table-column label="参数数" width="80">
          <template #default="{ row }">
            {{ Object.keys(row.params).length }}
          </template>
        </el-table-column>
        <el-table-column label="结果" width="100">
          <template #default="{ row }">
            <template v-if="row.results">
              <el-tag
                v-if="allPass(row.results)"
                type="success"
                size="small"
              >
                pass
              </el-tag>
              <el-tag v-else type="danger" size="small">fail</el-tag>
            </template>
            <span v-else>—</span>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          :disabled="loading"
          layout="total, sizes, prev, pager, next"
          @current-change="fetchRecords"
          @size-change="fetchRecords"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { queryRecords, listDevices, type AnalysisRecord } from '@/api/records'

const loading = ref(false)
const records = ref<AnalysisRecord[]>([])
const devices = ref<string[]>([])

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0,
})

const filters = reactive({
  barcode: '',
  device_id: '',
})

const timeRange = ref<[Date, Date] | null>([new Date(Date.now() - 604800000), new Date()])

const timeShortcuts = [
  { text: '近一天', value: () => [new Date(Date.now() - 86400000), new Date()] },
  { text: '最近一周', value: () => [new Date(Date.now() - 604800000), new Date()] },
  { text: '一个月', value: () => [new Date(Date.now() - 2592000000), new Date()] },
]

function allPass(results: Record<string, string | number>): boolean {
  return Object.values(results).every((v) => v === 'pass')
}

async function fetchRecords() {
  loading.value = true
  try {
    const params: Record<string, unknown> = {
      page: pagination.page,
      page_size: pagination.page_size,
    }
    if (filters.barcode) params.barcode = filters.barcode
    if (filters.device_id) params.device_id = filters.device_id
    if (timeRange.value) {
      params.start_time = timeRange.value[0].toISOString()
      params.end_time = timeRange.value[1].toISOString()
    }
    const data = await queryRecords(params)
    records.value = data.items
    pagination.total = data.total
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pagination.page = 1
  fetchRecords()
}

function handleReset() {
  filters.barcode = ''
  filters.device_id = ''
  timeRange.value = null
  pagination.page = 1
  fetchRecords()
}

onMounted(async () => {
  try {
    devices.value = await listDevices()
  } catch {
    // Silently fail — devices list is not critical
  }
  await fetchRecords()
})
</script>

<style scoped>
.data-view {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.filter-card {
  flex-shrink: 0;
  margin-bottom: 12px;
}
.table-card {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.table-card :deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 12px;
}
.table-card :deep(.el-table) {
  flex: 1;
  min-height: 0;
}
.table-card :deep(.el-table__body-wrapper) {
  overflow-y: auto;
}
.table-card :deep(.el-table .cell) {
  white-space: nowrap;
}
.detail-panel {
  padding: 8px 16px;
}
.results-desc {
  margin-top: 8px;
}
.pagination-wrapper {
  flex-shrink: 0;
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}
</style>

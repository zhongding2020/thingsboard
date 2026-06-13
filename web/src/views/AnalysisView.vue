<template>
  <div class="analysis">
    <div class="analysis-header">
      <h2 class="page-title">参数调优</h2>
      <p class="page-desc">工艺参数统计分析与优化</p>
    </div>

    <el-tabs v-model="mode" class="mode-tabs">
      <el-tab-pane label="在线分析" name="db">
        <AnalysisFilter />
        <el-tabs v-model="activeTab" class="analysis-tabs">
          <el-tab-pane label="字段概览" name="profile">
            <div v-if="profileFields.length" class="profile-grid">
              <el-card v-for="stat in profileFields" :key="stat.field" class="profile-card">
                <template #header>
                  <span class="profile-field">{{ stat.field }}</span>
                  <el-tag size="small" class="profile-dtype">{{ stat.dtype }}</el-tag>
                </template>
                <div class="profile-stats">
                  <div class="profile-stat">
                    <span class="profile-stat-label">Count</span>
                    <span class="profile-stat-value">{{ stat.count }}</span>
                  </div>
                  <div class="profile-stat" v-if="stat.mean !== null">
                    <span class="profile-stat-label">Mean</span>
                    <span class="profile-stat-value">{{ stat.mean.toFixed(4) }}</span>
                  </div>
                  <div class="profile-stat" v-if="stat.std !== null">
                    <span class="profile-stat-label">Std</span>
                    <span class="profile-stat-value">{{ stat.std.toFixed(4) }}</span>
                  </div>
                  <div class="profile-stat" v-if="stat.min !== null">
                    <span class="profile-stat-label">Min</span>
                    <span class="profile-stat-value">{{ stat.min }}</span>
                  </div>
                  <div class="profile-stat" v-if="stat.max !== null">
                    <span class="profile-stat-label">Max</span>
                    <span class="profile-stat-value">{{ stat.max }}</span>
                  </div>
                  <div class="profile-stat" v-if="stat.missing_count > 0">
                    <span class="profile-stat-label">Missing</span>
                    <span class="profile-stat-value">{{ stat.missing_count }} ({{ (stat.missing_rate * 100).toFixed(1) }}%)</span>
                  </div>
                  <div class="profile-stat" v-if="stat.iqr_outliers > 0">
                    <span class="profile-stat-label">Outliers</span>
                    <span class="profile-stat-value" style="color: var(--el-color-danger)">{{ stat.iqr_outliers }}</span>
                  </div>
                </div>
              </el-card>
            </div>
            <el-empty v-else description="请选择参数和结果后点击查询" :image-size="80" />
          </el-tab-pane>
          <el-tab-pane label="相关性" name="correlation">
            <CorrelationChart />
          </el-tab-pane>
          <el-tab-pane label="回归分析" name="regression">
            <RegressionChart />
          </el-tab-pane>
          <el-tab-pane label="参数推荐" name="recommendation">
            <RecommendationForm />
          </el-tab-pane>
        </el-tabs>
      </el-tab-pane>

      <el-tab-pane label="手动分析" name="excel">
        <div v-if="!datasetId" class="excel-upload-area">
          <el-card shadow="hover">
            <el-upload
              drag
              :auto-upload="false"
              :limit="1"
              accept=".xlsx,.xls"
              :on-change="handleFileChange"
              :file-list="fileList"
              class="full-upload"
            >
              <div class="upload-inline">
                <el-icon size="16"><UploadFilled /></el-icon>
                <span>拖拽或点击选择 .xlsx / .xls 文件</span>
              </div>
            </el-upload>
            <div class="excel-actions">
              <el-button type="primary" size="small" @click="handleUpload" :loading="uploading" :disabled="!fileList.length">
                上传并分析
              </el-button>
              <el-button size="small" @click="downloadTemplate">下载模板</el-button>
            </div>
            <div v-if="uploadError" class="upload-error">{{ uploadError }}</div>
          </el-card>
        </div>

        <div v-else>
          <el-card shadow="hover" class="upload-result">
            <div class="upload-result-info">
              <el-icon size="18" color="#059669"><CircleCheckFilled /></el-icon>
              <span>已上传 {{ sampleCount }} 条数据</span>
              <span class="field-count">{{ features.length }} 个参数 / {{ targets.length }} 个结果</span>
              <el-button text size="small" @click="resetUpload">重新上传</el-button>
            </div>
          </el-card>
          <el-tabs v-model="activeTab" class="analysis-tabs">
            <el-tab-pane label="字段概览" name="profile">
              <div v-if="profileFields.length" class="profile-grid">
                <el-card v-for="stat in profileFields" :key="stat.field" class="profile-card">
                  <template #header>
                    <span class="profile-field">{{ stat.field }}</span>
                    <el-tag size="small" class="profile-dtype">{{ stat.dtype }}</el-tag>
                  </template>
                  <div class="profile-stats">
                    <div class="profile-stat">
                      <span class="profile-stat-label">Count</span>
                      <span class="profile-stat-value">{{ stat.count }}</span>
                    </div>
                    <div class="profile-stat" v-if="stat.mean !== null">
                      <span class="profile-stat-label">Mean</span>
                      <span class="profile-stat-value">{{ stat.mean.toFixed(4) }}</span>
                    </div>
                    <div class="profile-stat" v-if="stat.std !== null">
                      <span class="profile-stat-label">Std</span>
                      <span class="profile-stat-value">{{ stat.std.toFixed(4) }}</span>
                    </div>
                    <div class="profile-stat" v-if="stat.min !== null">
                      <span class="profile-stat-label">Min</span>
                      <span class="profile-stat-value">{{ stat.min }}</span>
                    </div>
                    <div class="profile-stat" v-if="stat.max !== null">
                      <span class="profile-stat-label">Max</span>
                      <span class="profile-stat-value">{{ stat.max }}</span>
                    </div>
                  </div>
                </el-card>
              </div>
              <el-empty v-else description="请先上传 Excel 文件" :image-size="80" />
            </el-tab-pane>
            <el-tab-pane label="相关性" name="correlation">
              <ExcelCorrelationChart :dataset-id="datasetId" :fields="fields" />
            </el-tab-pane>
            <el-tab-pane label="回归分析" name="regression">
              <ExcelRegressionChart :dataset-id="datasetId" :fields="fields" />
            </el-tab-pane>
            <el-tab-pane label="参数推荐" name="recommendation">
              <ExcelRecommendationForm :dataset-id="datasetId" :fields="fields" />
            </el-tab-pane>
          </el-tabs>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useAnalysisStore, type ProfilingEntry } from '@/stores/analysis'
import AnalysisFilter from '@/components/AnalysisFilter.vue'
import CorrelationChart from '@/components/CorrelationChart.vue'
import RegressionChart from '@/components/RegressionChart.vue'
import RecommendationForm from '@/components/RecommendationForm.vue'
import ExcelCorrelationChart from '@/components/ExcelCorrelationChart.vue'
import ExcelRegressionChart from '@/components/ExcelRegressionChart.vue'
import ExcelRecommendationForm from '@/components/ExcelRecommendationForm.vue'
import { uploadExcel, excelProfile } from '@/api/analysis'
import { UploadFilled, CircleCheckFilled } from '@element-plus/icons-vue'
import type { UploadFile } from 'element-plus'

const analysis = useAnalysisStore()
const activeTab = ref('profile')
const mode = ref('db')

const datasetId = ref('')
const fileList = ref<UploadFile[]>([])
const uploading = ref(false)
const uploadError = ref('')
const features = ref<string[]>([])
const targets = ref<string[]>([])
const sampleCount = ref(0)

interface ExcelFields {
  features: string[]
  targets: string[]
}

const fields = computed<ExcelFields>(() => ({
  features: features.value,
  targets: targets.value,
}))

const profileFields = computed<ProfilingEntry[]>(() => {
  const r = analysis.profileResult
  if (!r || !Array.isArray(r)) return []
  return r as unknown as ProfilingEntry[]
})

function handleFileChange(file: UploadFile) {
  fileList.value = [file]
  uploadError.value = ''
}

async function handleUpload() {
  const f = fileList.value[0]?.raw
  if (!f) return
  uploading.value = true
  uploadError.value = ''
  try {
    const result = await uploadExcel(f)
    datasetId.value = result.dataset_id
    features.value = result.fields.features
    targets.value = result.fields.targets
    sampleCount.value = result.sample_count

    const profileResult = await excelProfile(result.dataset_id)
    analysis.profileResult = profileResult as unknown as Record<string, Record<string, unknown>>
  } catch (e: any) {
    uploadError.value = e?.response?.data?.message || e?.message || '上传失败'
  } finally {
    uploading.value = false
  }
}

function resetUpload() {
  datasetId.value = ''
  fileList.value = []
  features.value = []
  targets.value = []
  sampleCount.value = 0
  analysis.profileResult = {}
}

function downloadTemplate() {
  const wb = [
    ['temperature', 'conveyor_speed', 'oxygen_ppm', 'solder_joint_quality', 'voiding_pct'],
    [220.5, 48.2, 187, 'pass', 'pass'],
    [215.0, 52.0, 195, 'pass', 'fail'],
  ]
  const csv = wb.map(r => r.join(',')).join('\n')
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'spc_template.csv'
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.analysis-header { margin-bottom: 12px; }
.page-title {
  font-family: 'Fira Code', monospace;
  font-size: 20px; font-weight: 600;
  color: var(--el-text-color-primary); margin: 0 0 2px;
}
.page-desc { font-size: 12px; color: var(--el-text-color-secondary); margin: 0; }
.mode-tabs { margin-top: 12px; }
.analysis-tabs { margin-top: 12px; }
.excel-upload-area { }
.full-upload { width: 100%; }
.full-upload :deep(.el-upload-dragger) {
  height: 30px; width: 100%; padding: 0 12px;
  display: flex; align-items: center;
}
.upload-inline {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: var(--el-text-color-secondary);
}
.excel-actions {
  margin-top: 10px; display: flex; gap: 8px; align-items: center;
}
.upload-error { margin-top: 8px; color: var(--el-color-danger); font-size: 13px; }
.upload-result { margin-bottom: 12px; }
.upload-result-info {
  display: flex; align-items: center; gap: 10px; font-size: 13px;
  color: var(--el-text-color-regular);
}
.field-count { color: var(--el-text-color-secondary); font-size: 12px; }
.upload-result :deep(.el-card__body) { padding: 10px 14px; }
.profile-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}
.profile-card { animation: cardIn 0.3s ease-out both; }
.profile-card :deep(.el-card__header) {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 14px;
}
.profile-field {
  font-family: 'Fira Code', monospace; font-size: 14px; font-weight: 500;
  color: var(--el-color-primary);
}
.profile-dtype { font-size: 10px; }
.profile-stats { display: flex; flex-direction: column; gap: 6px; }
.profile-stat {
  display: flex; justify-content: space-between; align-items: center;
  padding: 3px 0; border-bottom: 1px solid var(--el-border-color-light);
}
.profile-stat:last-child { border-bottom: none; }
.profile-stat-label { font-size: 12px; color: var(--el-text-color-secondary); text-transform: capitalize; }
.profile-stat-value {
  font-family: 'Fira Code', monospace; font-size: 13px;
  color: var(--el-text-color-primary); font-weight: 500;
}
@keyframes cardIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>

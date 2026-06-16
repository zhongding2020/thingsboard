<template>
  <div class="analysis">
    <div class="analysis-header">
      <h2 class="page-title">参数调优</h2>
      <p class="page-desc">工艺参数统计分析与优化</p>
    </div>

    <el-steps :active="stepIndex" align-center class="analysis-steps" size="small">
      <el-step title="导入数据" description="在线查询或上传Excel" />
      <el-step title="数据预览" description="查看原始数据" />
      <el-step title="配置分析" description="选择字段与参数" />
      <el-step title="分析报告" description="结果分析与推荐" />
    </el-steps>

    <!-- Step 1: Import -->
    <div v-if="state === 'import'" class="step-wrap">
      <div class="import-cards">
        <el-card shadow="hover" class="import-card" :class="{ active: importMode === 'db' }" @click="importMode = 'db'">
          <el-icon :size="28" class="import-icon" color="#3B82F6"><DataBoard /></el-icon>
          <h3>在线查询</h3>
          <p>从数据库查询设备历史数据</p>
          <div class="import-body" :class="{ 'body-hidden': importMode !== 'db' }">
            <el-form inline>
              <el-form-item label="设备">
                <el-select v-model="filterDevice" placeholder="选择设备" style="width: 200px">
                  <el-option v-for="d in devices" :key="d" :label="d" :value="d" />
                </el-select>
              </el-form-item>
              <el-form-item label="时间范围">
                <el-date-picker
                  v-model="dateRange"
                  type="datetimerange"
                  range-separator="至"
                  start-placeholder="开始时间"
                  end-placeholder="结束时间"
                  :shortcuts="timeShortcuts"
                />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="handleOnlineQuery" :loading="loading">查询数据</el-button>
              </el-form-item>
            </el-form>
            <div v-if="importError" class="import-error">{{ importError }}</div>
          </div>
        </el-card>
        <el-card shadow="hover" class="import-card" :class="{ active: importMode === 'excel' }" @click="importMode = 'excel'">
          <el-icon :size="28" class="import-icon" color="#10B981"><FolderOpened /></el-icon>
          <h3>上传 Excel</h3>
          <p>拖拽 .xlsx / .xls 文件解析数据</p>
          <div class="import-body" :class="{ 'body-hidden': importMode !== 'excel' }">
            <el-upload drag :auto-upload="false" :limit="1" accept=".xlsx,.xls" :on-change="handleFileChange" :file-list="fileList">
              <div class="upload-hint">
                <el-icon size="20"><UploadFilled /></el-icon>
                <span>拖拽或点击选择文件</span>
              </div>
            </el-upload>
            <el-button type="primary" @click="handleExcelUpload" :loading="loading" :disabled="!fileList.length" style="margin-top: 8px;">
              上传解析
            </el-button>
            <div v-if="importError" class="import-error">{{ importError }}</div>
          </div>
        </el-card>
      </div>
    </div>

    <!-- Step 2: Preview -->
    <div v-if="state === 'preview'" class="step-wrap">
      <div class="step-header">
        <div>
          <span class="step-num">2</span>
          <span class="step-title">数据预览</span>
        </div>
        <el-button text size="small" @click="goImport">← 重新导入</el-button>
      </div>
      <DataPreviewTable
        :rows="previewRows"
        :total="previewTotal"
        :size="50"
        :page="previewPage"
        :fields="previewFields"
        :loading="previewLoading"
        @page-change="handlePreviewPage"
        @confirm="goConfig"
      />
    </div>

    <!-- Step 3: Config -->
    <div v-if="state === 'config'" class="step-wrap">
      <div class="step-header">
        <div>
          <span class="step-num">3</span>
          <span class="step-title">配置分析参数</span>
        </div>
        <el-button text size="small" @click="state = 'preview'">← 返回预览</el-button>
      </div>
      <FieldCheckboxGrid
        :fields="previewFields"
        @update:selected-features="selectedFeatures = $event"
        @update:selected-targets="selectedTargets = $event"
      />
      <div class="spec-section">
        <h4 style="font-size:13px;font-weight:600;margin:12px 0 8px;color:var(--el-text-color-primary);">Cpk 优化规格限</h4>
        <el-form inline size="small">
          <el-form-item label="目标字段">
            <el-select v-model="cfgTargetField" style="width: 160px">
              <el-option v-for="f in selectedTargets" :key="f" :label="f" :value="f" />
            </el-select>
          </el-form-item>
          <el-form-item label="USL">
            <el-input-number v-model="cfgUsl" :min="0" :step="1" style="width: 120px" />
          </el-form-item>
          <el-form-item label="LSL">
            <el-input-number v-model="cfgLsl" :min="0" :step="1" style="width: 120px" />
          </el-form-item>
          <el-form-item label="目标值">
            <el-input-number v-model="cfgTargetValue" :min="0" :step="0.5" style="width: 120px" />
          </el-form-item>
        </el-form>
      </div>
      <div class="config-actions">
        <el-button type="primary" size="large" @click="goReport" :loading="analyzing">
          <el-icon style="margin-right: 4px;"><Search /></el-icon> 开始分析
        </el-button>
      </div>
    </div>

    <!-- Step 4: Loading -->
    <div v-if="state === 'loading'" class="step-wrap loading-state">
      <el-icon class="is-loading" size="28"><Loading /></el-icon>
      <p>正在执行分析... {{ loadingProgress }}</p>
    </div>

    <!-- Step 5: Report -->
    <div v-if="state === 'report'" class="report-wrap">
      <div class="step-header">
        <div>
          <span class="step-num">4</span>
          <span class="step-title">分析报告</span>
        </div>
        <div class="step-actions">
          <el-button text size="small" @click="state = 'config'">调整参数</el-button>
          <el-button text size="small" @click="goImport">重新导入</el-button>
        </div>
      </div>
      <div class="report-layout">
        <nav class="report-nav">
          <a v-for="item in navItems" :key="item.id" :href="'#' + item.id" class="nav-item" :class="{ active: activeNav === item.id }" @click.prevent="scrollTo(item.id)">
            <el-icon :size="14" :style="{ color: item.color }"><component :is="item.icon" /></el-icon> {{ item.label }}
          </a>
        </nav>
        <div class="report-content" ref="reportContentRef" @scroll="onReportScroll">
          <section id="report-overview">
            <h3><el-icon :size="16" color="#3B82F6"><Document /></el-icon> 数据概览</h3>
            <el-row :gutter="12">
              <el-col :span="6"><el-card><div class="stat-num">{{ sampleCount }}</div><div class="stat-label">样本数</div></el-card></el-col>
              <el-col :span="6"><el-card><div class="stat-num" style="color: var(--el-color-primary)">{{ selectedFeatures.length }}</div><div class="stat-label">参数字段</div></el-card></el-col>
              <el-col :span="6"><el-card><div class="stat-num" style="color: #a855f7">{{ selectedTargets.length }}</div><div class="stat-label">结果字段</div></el-card></el-col>
              <el-col :span="6"><el-card><div class="stat-num" style="color: var(--el-color-warning)">{{ missingCount }}</div><div class="stat-label">缺失值</div></el-card></el-col>
            </el-row>
          </section>
          <section id="report-profile">
            <h3><el-icon :size="16" color="#8B5CF6"><DataAnalysis /></el-icon> 字段分析</h3>
            <div v-if="profileData.length" class="profile-grid">
              <el-card v-for="stat in profileData" :key="stat.field" class="profile-card" shadow="hover">
                <template #header>
                  <span class="profile-field">{{ stat.field }}</span>
                </template>
                <div class="profile-stats">
                  <div class="profile-stat"><span>Mean</span><span>{{ stat.mean?.toFixed(4) ?? '—' }}</span></div>
                  <div class="profile-stat"><span>Std</span><span>{{ stat.std?.toFixed(4) ?? '—' }}</span></div>
                  <div class="profile-stat"><span>Min</span><span>{{ stat.min ?? '—' }}</span></div>
                  <div class="profile-stat"><span>Max</span><span>{{ stat.max ?? '—' }}</span></div>
                  <div class="profile-stat"><span>Missing</span><span>{{ stat.missing_count }} ({{ (stat.missing_rate * 100).toFixed(1) }}%)</span></div>
                </div>
              </el-card>
            </div>
            <el-empty v-else description="无分析数据" :image-size="60" />
          </section>
          <section id="report-correlation">
            <h3><el-icon :size="16" color="#10B981"><Link /></el-icon> 相关性</h3>
            <CorrelationChart :dataset-id="datasetId!" :feature-fields="selectedFeatures" :target-fields="selectedTargets" :auto-mode="true" />
          </section>
          <section id="report-pareto">
            <h3><el-icon :size="16" color="#F59E0B"><Histogram /></el-icon> 帕累托图</h3>
            <ParetoChart
              :dataset-id="datasetId!"
              :target-fields="selectedTargets"
              :auto-mode="true"
            />
          </section>
          <section id="report-cpk">
            <h3><el-icon :size="16" color="#EF4444"><Aim /></el-icon> Cpk 优化</h3>
            <CpkOptimizer
              :dataset-id="datasetId!"
              :feature-fields="selectedFeatures"
              :target-field="cfgTargetField"
              :usl="cfgUsl"
              :lsl="cfgLsl"
              :target-value="cfgTargetValue"
            />
          </section>
          <section id="report-regression">
            <h3><el-icon :size="16" color="#F59E0B"><TrendCharts /></el-icon> 回归分析</h3>
            <RegressionChart :dataset-id="datasetId!" :feature-fields="selectedFeatures" :target-fields="selectedTargets" :auto-mode="true" />
          </section>
          <section id="report-recommendation">
            <h3><el-icon :size="16" color="#EC4899"><MagicStick /></el-icon> 参数推荐</h3>
            <RecommendationForm :dataset-id="datasetId!" :feature-fields="selectedFeatures" :target-fields="selectedTargets" />
          </section>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { queryDataset, uploadDataset, previewDataset, profile as apiProfile, type PreviewResponse } from '@/api/analysis'
import { listDevices as fetchDevices } from '@/api/records'
import DataPreviewTable from '@/components/DataPreviewTable.vue'
import FieldCheckboxGrid from '@/components/FieldCheckboxGrid.vue'
import CorrelationChart from '@/components/CorrelationChart.vue'
import RegressionChart from '@/components/RegressionChart.vue'
import RecommendationForm from '@/components/RecommendationForm.vue'
import ParetoChart from '@/components/ParetoChart.vue'
import CpkOptimizer from '@/components/CpkOptimizer.vue'
import { UploadFilled, Loading, DataBoard, FolderOpened, Search, Document, DataAnalysis, Link, TrendCharts, MagicStick, Histogram, Aim } from '@element-plus/icons-vue'
import type { UploadFile } from 'element-plus'

type Step = 'import' | 'preview' | 'config' | 'loading' | 'report'

const state = ref<Step>('import')
const stepIndex = computed(() => {
  const map: Record<Step, number> = { import: 0, preview: 1, config: 2, loading: 3, report: 3 }
  return map[state.value]
})
const importMode = ref<'db' | 'excel'>('db')
const loading = ref(false)
const importError = ref('')
const analyzing = ref(false)
const loadingProgress = ref('')

const devices = ref<string[]>([])
const filterDevice = ref('')
const dateRange = ref<[Date, Date] | null>([new Date(Date.now() - 604800000), new Date()])
const fileList = ref<UploadFile[]>([])

const timeShortcuts = [
  { text: '近一天', value: () => [new Date(Date.now() - 86400000), new Date()] },
  { text: '最近一周', value: () => [new Date(Date.now() - 604800000), new Date()] },
  { text: '一个月', value: () => [new Date(Date.now() - 2592000000), new Date()] },
]

const datasetId = ref<string | null>(null)
const sampleCount = ref(0)

const previewRows = ref<Record<string, unknown>[]>([])
const previewTotal = ref(0)
const previewPage = ref(1)
const previewLoading = ref(false)
const previewFields = ref<PreviewResponse['fields']>({ features: [], targets: [] })

const selectedFeatures = ref<string[]>([])
const selectedTargets = ref<string[]>([])

const profileData = ref<{ field: string; mean: number | null; std: number | null; min: number | null; max: number | null; missing_count: number; missing_rate: number }[]>([])
const missingCount = ref(0)
const cfgTargetField = ref('')
const cfgUsl = ref(100)
const cfgLsl = ref(0)
const cfgTargetValue = ref(50)

const activeNav = ref('report-overview')
const reportContentRef = ref<HTMLElement | null>(null)

const navItems = [
  { id: 'report-overview', icon: Document, label: '数据概览', color: '#3B82F6' },
  { id: 'report-profile', icon: DataAnalysis, label: '字段分析', color: '#8B5CF6' },
  { id: 'report-correlation', icon: Link, label: '相关性', color: '#10B981' },
  { id: 'report-pareto', icon: Histogram, label: '帕累托图', color: '#F59E0B' },
  { id: 'report-cpk', icon: Aim, label: 'Cpk 优化', color: '#EF4444' },
  { id: 'report-regression', icon: TrendCharts, label: '回归', color: '#F59E0B' },
  { id: 'report-recommendation', icon: MagicStick, label: '推荐', color: '#EC4899' },
]

async function loadDevices() {
  try {
    devices.value = await fetchDevices()
    if (devices.value.length && !filterDevice.value) {
      filterDevice.value = devices.value[0]
    }
  } catch {
    // silent
  }
}

function handleFileChange(file: UploadFile) {
  fileList.value = [file]
  importError.value = ''
}

async function handleOnlineQuery() {
  if (!filterDevice.value) return
  loading.value = true
  importError.value = ''
  try {
    const since = dateRange.value?.[0]?.toISOString()
    const r = await queryDataset(filterDevice.value, since)
    setDataset(r)
  } catch (e: any) {
    importError.value = e?.response?.data?.message || e?.message || '查询失败'
  } finally {
    loading.value = false
  }
}

async function handleExcelUpload() {
  const f = fileList.value[0]?.raw
  if (!f) return
  loading.value = true
  importError.value = ''
  try {
    const r = await uploadDataset(f)
    setDataset(r)
  } catch (e: any) {
    importError.value = e?.response?.data?.message || e?.message || '上传失败'
  } finally {
    loading.value = false
  }
}

function setDataset(r: { dataset_id: string; fields: { features: string[]; targets: string[] }; sample_count: number }) {
  datasetId.value = r.dataset_id
  sampleCount.value = r.sample_count
  state.value = 'preview'
  loadPreview()
}

async function loadPreview() {
  if (!datasetId.value) return
  previewLoading.value = true
  try {
    const r = await previewDataset(datasetId.value, previewPage.value, 50)
    previewRows.value = r.rows
    previewTotal.value = r.total
    previewFields.value = r.fields
  } finally {
    previewLoading.value = false
  }
}

async function handlePreviewPage(page: number) {
  previewPage.value = page
  await loadPreview()
}

function goConfig() {
  state.value = 'config'
  selectedFeatures.value = previewFields.value.features.map((f) => f.name)
  selectedTargets.value = previewFields.value.targets.filter((f) => f.type === 'numeric').map((f) => f.name)
  if (selectedTargets.value.length) {
    cfgTargetField.value = selectedTargets.value[0]
  }
}

async function goReport() {
  if (!datasetId.value || !selectedFeatures.value.length || !selectedTargets.value.length) return
  state.value = 'loading'
  analyzing.value = true
  loadingProgress.value = ''
  try {
    loadingProgress.value = '1/4 字段分析...'
    const pf = await apiProfile(datasetId.value) as { field: string; mean: number | null; std: number | null; min: number | null; max: number | null; missing_count: number; missing_rate: number }[]
    profileData.value = pf
    missingCount.value = pf.reduce((s, x) => s + (x.missing_count || 0), 0)

    state.value = 'report'
    await nextTick()
    activeNav.value = 'report-overview'
  } finally {
    analyzing.value = false
    loadingProgress.value = ''
  }
}

function goImport() {
  state.value = 'import'
  datasetId.value = null
  previewRows.value = []
  previewFields.value = { features: [], targets: [] }
  selectedFeatures.value = []
  selectedTargets.value = []
  profileData.value = []
  importError.value = ''
  fileList.value = []
}

function scrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })
  activeNav.value = id
}

function onReportScroll() {
  const el = reportContentRef.value
  if (!el) return
  for (const item of [...navItems].reverse()) {
    const section = document.getElementById(item.id)
    if (section && section.offsetTop <= el.scrollTop + 100) {
      activeNav.value = item.id
      break
    }
  }
}

onMounted(loadDevices)
</script>

<style scoped>
.analysis-header { margin-bottom: 8px; }
.page-title { font-family: 'Fira Code', monospace; font-size: 18px; font-weight: 600; margin: 0; color: var(--el-text-color-primary); }
.page-desc { font-size: 11px; color: var(--el-text-color-secondary); margin: 0; }

.analysis-steps { margin: 4px 0 8px; }
.analysis-steps :deep(.el-step) { flex-basis: auto !important; }
.analysis-steps :deep(.el-step__head) { width: 22px; height: 22px; }
.analysis-steps :deep(.el-step__icon) { width: 22px; height: 22px; font-size: 11px; }
.analysis-steps :deep(.el-step__main) { padding: 0 4px; }
.analysis-steps :deep(.el-step__title) { font-size: 12px; line-height: 1.3; }
.analysis-steps :deep(.el-step__description) { padding-top: 0; font-size: 10px; line-height: 1.2; }
.analysis-steps :deep(.el-step__line) { top: 11px; }

.step-wrap { margin-top: 8px; }
.step-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.step-num { display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; background: var(--el-color-primary); border-radius: 50%; color: #fff; font-size: 11px; font-weight: 600; margin-right: 6px; }
.step-title { font-size: 14px; font-weight: 600; color: var(--el-text-color-primary); }
.step-actions { display: flex; gap: 6px; }

.import-cards { display: flex; gap: 12px; }
.import-card { flex: 1; display: flex; flex-direction: column; min-height: 160px; padding: 4px; cursor: pointer; border: 2px solid transparent; transition: border-color 0.2s; }
.import-card :deep(.el-card__body) { display: flex; flex-direction: column; flex: 1; padding: 12px; }
.import-card.active { border-color: var(--el-color-primary); }
.import-card h3 { margin: 2px 0; font-size: 14px; }
.import-card p { font-size: 11px; color: var(--el-text-color-secondary); margin: 0 0 6px; }
.import-icon { margin-bottom: 2px; }
.import-body { margin-top: 6px; flex: 1; }
.body-hidden { visibility: hidden; pointer-events: none; }
.import-error { color: var(--el-color-danger); font-size: 11px; margin-top: 6px; }
.upload-hint { display: flex; flex-direction: column; align-items: center; gap: 2px; font-size: 11px; color: var(--el-text-color-secondary); padding: 8px; }

.config-actions { margin-top: 12px; display: flex; justify-content: flex-end; }

.loading-state { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 140px; gap: 8px; font-size: 13px; color: var(--el-text-color-secondary); }

.report-wrap { margin-top: 8px; }
.report-layout { display: flex; gap: 12px; margin-top: 8px; }
.report-nav { width: 120px; flex-shrink: 0; }
.report-nav .nav-item { display: block; padding: 4px 8px; font-size: 11px; color: var(--el-text-color-secondary); text-decoration: none; border-left: 2px solid transparent; cursor: pointer; transition: all 0.2s; }
.report-nav .nav-item:hover { color: var(--el-color-primary); }
.report-nav .nav-item.active { color: var(--el-color-primary); border-left-color: var(--el-color-primary); font-weight: 500; }
.report-content { flex: 1; max-height: calc(100vh - 160px); overflow-y: auto; }
.report-content section { margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid var(--el-border-color-light); }
.report-content section:last-child { border-bottom: none; }
.report-content h3 { font-size: 14px; font-weight: 600; margin: 0 0 8px; }

.stat-num { font-family: 'Fira Code', monospace; font-size: 20px; font-weight: 700; text-align: center; }
.stat-label { font-size: 10px; color: var(--el-text-color-secondary); text-align: center; margin-top: 2px; }

.profile-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 6px; }
.profile-card :deep(.el-card__header) { padding: 6px 10px; }
.profile-card :deep(.el-card__body) { padding: 8px 10px; }
.profile-field { font-family: 'Fira Code', monospace; font-size: 12px; font-weight: 500; color: var(--el-color-primary); }
.profile-stats { display: flex; flex-direction: column; gap: 2px; }
.profile-stat { display: flex; justify-content: space-between; font-size: 11px; padding: 1px 0; border-bottom: 1px solid var(--el-border-color-light); }
.profile-stat span:first-child { color: var(--el-text-color-secondary); }
.profile-stat span:last-child { font-family: 'Fira Code', monospace; font-weight: 500; }
</style>

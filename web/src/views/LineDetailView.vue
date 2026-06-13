<template>
  <div class="line-detail-view">
    <div class="page-header">
      <div>
        <router-link to="/lines" class="back-link">← 返回线体列表</router-link>
        <h2 class="page-title">{{ line?.name || '加载中...' }}</h2>
        <p class="page-desc">责任人: {{ line?.responsible }} · 位置: {{ line?.location || '未设置' }}</p>
      </div>
      <el-button v-if="line" text @click="openEditLine">编辑线体</el-button>
    </div>

    <div v-if="line" class="overview-cards">
      <el-card><div class="stat-value">{{ devices.length }}</div><div class="stat-label">设备总数</div></el-card>
      <el-card><div class="stat-value" style="color:#059669">{{ normalCount }}</div><div class="stat-label">正常</div></el-card>
      <el-card><div class="stat-value" style="color:#DC2626">{{ abnormalCount }}</div><div class="stat-label">异常</div></el-card>
      <el-card><div class="stat-value" style="color:#D97706">{{ marginalCount }}</div><div class="stat-label">边缘</div></el-card>
    </div>

    <el-card class="devices-card">
      <template #header>
        <div class="devices-header">
          <span>设备列表</span>
          <el-button size="small" @click="openManageDevices">管理设备</el-button>
        </div>
      </template>
      <el-table :data="devices" stripe size="small" v-loading="loading" empty-text="暂无设备">
        <el-table-column prop="name" label="设备名称" min-width="140" class-name="cell-mono">
          <template #default="{ row }">
            <router-link :to="`/spc?line=${line!.id}&device=${row.id}`" class="device-link">
              {{ row.name }}
            </router-link>
          </template>
        </el-table-column>
        <el-table-column prop="type" label="设备类型" width="140" class-name="cell-mono" />
        <el-table-column prop="description" label="描述" min-width="160" class-name="cell-mono">
          <template #default="{ row }">{{ row.description || '—' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button text size="small" @click="openEditDevice(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="lineDialogVisible" title="编辑线体" width="480px">
      <el-form :model="lineForm" label-width="80px">
        <el-form-item label="名称"><el-input v-model="lineForm.name" /></el-form-item>
        <el-form-item label="责任人"><el-input v-model="lineForm.responsible" /></el-form-item>
        <el-form-item label="位置"><el-input v-model="lineForm.location" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="lineDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveLine" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="deviceDialogVisible" title="编辑设备" width="480px">
      <el-form :model="deviceForm" label-width="80px">
        <el-form-item label="名称"><el-input v-model="deviceForm.name" /></el-form-item>
        <el-form-item label="类型"><el-input v-model="deviceForm.type" /></el-form-item>
        <el-form-item label="图标"><el-input v-model="deviceForm.icon" placeholder="Element Plus icon name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="deviceForm.description" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="deviceDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveDevice" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="manageDialogVisible" title="管理设备" width="560px">
      <el-table :data="allDevices" stripe size="small">
        <el-table-column prop="name" label="设备" class-name="cell-mono" />
        <el-table-column prop="line_name" label="所属线体" width="140" class-name="cell-mono">
          <template #default="{ row }">{{ row.line_name || '未分配' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button v-if="row.line_id !== line!.id" text size="small" type="primary" @click="assignDevice(row)">分配到本线</el-button>
            <el-button v-else text size="small" type="danger" @click="unassignDevice(row)">移出</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { getLine, updateLine, listDevices, updateDevice, type LineDetailResponse, type DeviceResponse } from '@/api/lines'

const route = useRoute()
const line = ref<LineDetailResponse | null>(null)
const devices = ref<DeviceResponse[]>([])
const allDevices = ref<DeviceResponse[]>([])
const loading = ref(false)
const saving = ref(false)
const lineDialogVisible = ref(false)
const deviceDialogVisible = ref(false)
const manageDialogVisible = ref(false)
const editingDevice = ref<DeviceResponse | null>(null)
const lineForm = ref({ name: '', responsible: '', location: '' })
const deviceForm = ref({ name: '', type: '', icon: '', description: '' })

const normalCount = computed(() => 0)
const abnormalCount = computed(() => 0)
const marginalCount = computed(() => 0)

async function loadLine() {
  loading.value = true
  try {
    const id = route.params.id as string
    line.value = await getLine(id)
    devices.value = line.value.devices
  } finally { loading.value = false }
}

function openEditLine() {
  if (!line.value) return
  lineForm.value = { name: line.value.name, responsible: line.value.responsible, location: line.value.location || '' }
  lineDialogVisible.value = true
}

async function saveLine() {
  if (!line.value) return
  saving.value = true
  try {
    await updateLine(line.value.id, lineForm.value)
    lineDialogVisible.value = false
    await loadLine()
  } finally { saving.value = false }
}

function openEditDevice(device: DeviceResponse) {
  editingDevice.value = device
  deviceForm.value = {
    name: device.name, type: device.type, icon: device.icon || '',
    description: device.description || '',
  }
  deviceDialogVisible.value = true
}

async function saveDevice() {
  if (!editingDevice.value) return
  saving.value = true
  try {
    await updateDevice(editingDevice.value.id, deviceForm.value)
    deviceDialogVisible.value = false
    await loadLine()
  } finally { saving.value = false }
}

async function openManageDevices() {
  allDevices.value = await listDevices()
  manageDialogVisible.value = true
}

async function assignDevice(device: DeviceResponse) {
  await updateDevice(device.id, { line_id: line.value!.id })
  await loadLine()
  allDevices.value = await listDevices()
}

async function unassignDevice(device: DeviceResponse) {
  await updateDevice(device.id, { line_id: '' })
  await loadLine()
  allDevices.value = await listDevices()
}

onMounted(loadLine)
</script>

<style scoped>
.line-detail-view { display: flex; flex-direction: column; gap: 12px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; }
.page-title { font-family: 'Fira Code', monospace; font-size: 20px; font-weight: 600; margin: 0; }
.page-desc { font-size: 13px; color: var(--el-text-color-secondary); margin: 2px 0 0; }
.back-link { font-size: 12px; color: var(--el-text-color-secondary); text-decoration: none; }
.back-link:hover { color: var(--el-color-primary); }
.overview-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.overview-cards .el-card { text-align: center; padding: 0; }
.overview-cards :deep(.el-card__body) { padding: 16px 8px; }
.stat-value { font-family: 'Fira Code', monospace; font-size: 28px; font-weight: 700; }
.stat-label { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 4px; }
.devices-header { display: flex; justify-content: space-between; align-items: center; }
.device-link { color: var(--el-color-primary); text-decoration: none; display: flex; align-items: center; gap: 4px; font-family: 'Fira Code', monospace; }
.device-link:hover { text-decoration: underline; }
</style>

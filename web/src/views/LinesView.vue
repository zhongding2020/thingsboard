<template>
  <div class="topo-view">
    <div class="page-header">
      <div>
        <h2 class="page-title">线体拓扑</h2>
        <p class="page-desc">产线设备布局 & 状态总览</p>
      </div>
      <el-button type="primary" @click="openCreate">+ 新建线体</el-button>
    </div>

    <div v-loading="loading" class="topo-canvas">
      <div v-for="line in lineData" :key="line.id" class="line-section">
        <div class="line-header">
          <div class="line-header-left">
            <span class="line-name">{{ line.name }}</span>
            <span class="line-meta">
              <el-icon size="13"><User /></el-icon> {{ line.responsible }}
              <span v-if="line.location"> · {{ line.location }}</span>
            </span>
          </div>
          <div class="line-header-right">
            <el-tag :type="lineStatusTag(line)" size="small">{{ lineStatusLabel(line) }}</el-tag>
            <el-button text size="small" @click="openEdit(line)"><el-icon><Edit /></el-icon></el-button>
            <el-button text size="small" type="danger" @click="handleDelete(line)" :disabled="line.devices.length > 0"><el-icon><Delete /></el-icon></el-button>
          </div>
        </div>

        <div class="line-devices">
          <div
            v-for="device in line.devices"
            :key="device.id"
            class="device-node"
            :class="{ 'device-dragging': dragState.deviceId === device.id }"
            draggable="true"
            @click.stop="goToSpc(line.id, device.id)"
            @dragstart="onDragStart($event, device.id, line.id)"
            @dragend="onDragEnd"
            @dragover.prevent="onDragOver($event, line.id)"
            @drop="onDrop($event, device.id, line.id)"
          >
            <div class="device-icon" :style="{ color: deviceColor(device.type) }">
              <el-icon size="22"><component :is="deviceIcon(device.type)" /></el-icon>
            </div>
            <div class="device-body">
              <span class="device-name">{{ device.name }}</span>
              <span class="device-type">{{ deviceLabel(device.type) }}</span>
            </div>
            <div class="device-actions">
              <el-button text size="small" @click.stop="openDeviceParam(device)" title="查看参数">
                <el-icon :size="13" color="var(--el-text-color-secondary)"><Setting /></el-icon>
              </el-button>
            </div>
            <div class="device-status">
              <span :class="['status-dot', `status-${device.status || 'normal'}`]" />
            </div>
          </div>
          <div v-if="!line.devices.length" class="device-empty">
            暂无设备 · <span class="add-device-link" @click.stop="openManageDevices(line)">添加设备</span>
          </div>
          <div class="device-node device-add-node" @click.stop="openManageDevices(line)">
            <el-icon size="18"><Plus /></el-icon>
          </div>
        </div>
      </div>
    </div>

    <!-- Line create/edit dialog -->
    <el-dialog v-model="dialogVisible" :title="editing ? '编辑线体' : '新建线体'" width="480px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="线体名称"><el-input v-model="form.name" placeholder="如 SMT-01" /></el-form-item>
        <el-form-item label="责任人"><el-input v-model="form.responsible" placeholder="负责人姓名" /></el-form-item>
        <el-form-item label="位置"><el-input v-model="form.location" placeholder="如 A栋2层" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">{{ editing ? '保存' : '创建' }}</el-button>
      </template>
    </el-dialog>

    <!-- Device assignment dialog -->
    <el-dialog v-model="manageVisible" title="管理设备" width="560px">
      <el-table :data="allDevices" stripe size="small">
        <el-table-column prop="name" label="设备" class-name="cell-mono" />
        <el-table-column prop="line_name" label="所属线体" width="140" class-name="cell-mono">
          <template #default="{ row }">{{ row.line_name || '未分配' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button v-if="row.line_id !== manageLineId" text size="small" type="primary" @click="assignToLine(row)">添加</el-button>
            <el-button v-else text size="small" type="danger" @click="removeFromLine(row)">移出</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <DeviceParameterDialog
      v-model="paramDialogVisible"
      :device-id="paramDeviceId"
      :device-type="paramDeviceType"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { User, Edit, Delete, Plus, Setting } from '@element-plus/icons-vue'
import { deviceIcon, deviceLabel, deviceColor } from '@/utils/device-icons'
import DeviceParameterDialog from '@/components/DeviceParameterDialog.vue'
import {
  listLines, createLine, updateLine, deleteLine,
  listDevices, updateDevice, reorderDevices,
  type LineResponse, type DeviceResponse,
} from '@/api/lines'

const router = useRouter()

interface LineWithDevices extends LineResponse {
  devices: (DeviceResponse & { status?: string })[]
}

const lineData = ref<LineWithDevices[]>([])
const allDevices = ref<DeviceResponse[]>([])
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const manageVisible = ref(false)
const manageLineId = ref('')
const editing = ref<LineResponse | null>(null)
const form = ref({ name: '', responsible: '', location: '' })

const dragState = reactive({ deviceId: '', fromLineId: '' })

const paramDialogVisible = ref(false)
const paramDeviceId = ref('')
const paramDeviceType = ref('')
function openDeviceParam(device: { id: string; type: string }) {
  paramDeviceId.value = device.id
  paramDeviceType.value = device.type
  paramDialogVisible.value = true
}

function onDragStart(e: DragEvent, deviceId: string, lineId: string) {
  if (!e.dataTransfer) return
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData('text/plain', deviceId)
  dragState.deviceId = deviceId
  dragState.fromLineId = lineId
}

function onDragEnd() {
  dragState.deviceId = ''
  dragState.fromLineId = ''
}

function onDragOver(e: DragEvent, _lineId: string) {
  if (!e.dataTransfer) return
  e.dataTransfer.dropEffect = 'move'
}

async function onDrop(_e: DragEvent, targetDeviceId: string, targetLineId: string) {
  if (!dragState.deviceId || dragState.deviceId === targetDeviceId) return

  const fromLine = lineData.value.find(l => l.id === dragState.fromLineId)
  const toLine = lineData.value.find(l => l.id === targetLineId)
  if (!fromLine || !toLine) return

  const fromIndex = fromLine.devices.findIndex(d => d.id === dragState.deviceId)
  if (fromIndex === -1) return

  const [moved] = fromLine.devices.splice(fromIndex, 1)

  if (dragState.fromLineId === targetLineId) {
    // Reorder within same line
    const toIndex = toLine.devices.findIndex(d => d.id === targetDeviceId)
    toLine.devices.splice(toIndex, 0, moved)
    try {
      await reorderDevices(targetLineId, toLine.devices.map(d => d.id))
    } catch {}
  } else {
    // Move to different line — assign to new line, append at end
    toLine.devices.push({ ...moved })
    try {
      await updateDevice(moved.id, { line_id: targetLineId })
      await reorderDevices(targetLineId, toLine.devices.map(d => d.id))
    } catch {}
  }

  dragState.deviceId = ''
  dragState.fromLineId = ''
}

async function loadAll() {
  loading.value = true
  try {
    const lines = await listLines()
    const allDevs = await listDevices()
    allDevices.value = allDevs

    const enriched: LineWithDevices[] = []
    for (const line of lines) {
      const devices = allDevs
        .filter(d => d.line_id === line.id)
        .map(d => ({ ...d, status: 'normal' as const }))
      enriched.push({ ...line, devices })
    }
    lineData.value = enriched
  } finally { loading.value = false }
}

function lineStatusTag(line: LineWithDevices) {
  return line.devices.length ? '' : 'info'
}

function lineStatusLabel(line: LineWithDevices) {
  return line.devices.length ? `${line.devices.length} 台设备` : '无设备'
}

function goToSpc(lineId: string, deviceId: string) {
  router.push(`/spc?line=${lineId}&device=${deviceId}`)
}

function openCreate() {
  editing.value = null
  form.value = { name: '', responsible: '', location: '' }
  dialogVisible.value = true
}

function openEdit(line: LineResponse) {
  editing.value = line
  form.value = { name: line.name, responsible: line.responsible, location: line.location || '' }
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
    await loadAll()
  } finally { saving.value = false }
}

async function handleDelete(line: LineResponse) {
  await deleteLine(line.id)
  await loadAll()
}

function openManageDevices(line: LineWithDevices) {
  manageLineId.value = line.id
  manageVisible.value = true
}

async function assignToLine(device: DeviceResponse) {
  await updateDevice(device.id, { line_id: manageLineId.value })
  await loadAll()
  allDevices.value = await listDevices()
}

async function removeFromLine(device: DeviceResponse) {
  await updateDevice(device.id, { line_id: '' })
  await loadAll()
  allDevices.value = await listDevices()
}

onMounted(loadAll)
</script>

<style scoped>
.topo-view { display: flex; flex-direction: column; gap: 12px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; }
.page-title { font-family: 'Fira Code', monospace; font-size: 20px; font-weight: 600; margin: 0; }
.page-desc { font-size: 13px; color: var(--el-text-color-secondary); margin: 2px 0 0; }

.topo-canvas { display: flex; flex-direction: column; gap: 16px; min-height: 200px; }

.line-section {
  background: var(--el-fill-color-blank);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  overflow: hidden;
  transition: border-color 0.2s;
}
.line-section:hover { border-color: var(--el-color-primary-light-5); }

.line-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 16px;
  background: var(--el-fill-color-light);
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.line-header-left { display: flex; align-items: center; gap: 12px; }
.line-name {
  font-family: 'Fira Code', monospace;
  font-size: 15px; font-weight: 600;
  color: var(--el-color-primary);
  cursor: pointer;
}
.line-name:hover { text-decoration: underline; }
.line-meta {
  font-size: 12px; color: var(--el-text-color-secondary);
  display: flex; align-items: center; gap: 4px;
}
.line-header-right { display: flex; align-items: center; gap: 6px; }

.line-devices {
  display: flex; flex-wrap: wrap; gap: 10px;
  padding: 12px 16px;
  min-height: 64px; align-items: flex-start;
  transition: background 0.15s;
}
.line-devices.drop-over { background: var(--el-color-primary-light-9); }

.device-node {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px;
  background: var(--el-fill-color);
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
  min-width: 160px;
}
.device-node:hover {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 2px var(--el-color-primary-light-8);
  transform: translateY(-1px);
}
.device-node.device-dragging {
  opacity: 0.4; border-style: dashed;
}
.device-icon {
  display: flex; align-items: center;
  transition: color 0.2s;
}
.device-body {
  display: flex; flex-direction: column; flex: 1;
}
.device-name {
  font-family: 'Fira Code', monospace;
  font-size: 12px; font-weight: 500;
  color: var(--el-text-color-primary);
}
.device-type {
  font-size: 10px; color: var(--el-text-color-secondary);
}
.device-status { margin-left: 4px; }
.status-dot {
  display: inline-block; width: 7px; height: 7px;
  border-radius: 50%; background: #059669;
}
.status-dot.status-abnormal { background: #DC2626; }
.status-dot.status-marginal { background: #D97706; }
.status-dot.status-no_spec { background: #94A3B8; }

.device-empty {
  display: flex; align-items: center; gap: 4px;
  padding: 8px 12px;
  font-size: 12px; color: var(--el-text-color-placeholder);
}
.add-device-link { color: var(--el-color-primary); cursor: pointer; }
.add-device-link:hover { text-decoration: underline; }

.device-add-node {
  min-width: 48px; justify-content: center;
  border: 1px dashed var(--el-border-color);
  color: var(--el-text-color-placeholder);
}
.device-add-node:hover { color: var(--el-color-primary); border-color: var(--el-color-primary); }

.manage-devices { margin-top: 8px; }
</style>

<template>
  <el-drawer v-model="visible" title="实验任务" size="450px">
    <template v-if="device">
      <div class="exp-device-info">
        <span>{{ device.name || device.device_id }}</span>
        <el-tag size="small" :type="device.status === 'running' ? 'success' : 'info'">{{ device.status }}</el-tag>
      </div>

      <el-divider />

      <!-- 分配实验 -->
      <div class="exp-section">
        <h4>分配实验计划</h4>
        <el-select v-model="selectedPlanId" placeholder="选择实验计划" style="width:100%" filterable>
          <el-option v-for="p in availablePlans" :key="p.id" :label="`#${p.id} ${p.name}`" :value="p.id" />
        </el-select>
        <el-button type="primary" :disabled="!selectedPlanId" :loading="assigning" @click="assignExperiment" style="margin-top:10px;width:100%">
          分配到设备
        </el-button>
      </div>

      <el-divider />

      <!-- 当前实验进度 -->
      <div class="exp-section">
        <h4>当前实验</h4>
        <div v-if="currentExp" class="exp-progress">
          <el-progress :percentage="currentExp.progress" :status="currentExp.status" />
          <p class="exp-detail">Plan #{{ currentExp.planId }}: {{ currentExp.done }}/{{ currentExp.total }} runs</p>
        </div>
        <el-empty v-else description="无进行中的实验" :image-size="60" />
      </div>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps<{ visible: boolean; device: any }>()
const emit = defineEmits(['update:visible'])

const visible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

const selectedPlanId = ref<number | null>(null)
const assigning = ref(false)
const availablePlans = ref<any[]>([])
const currentExp = ref<any>(null)

watch(() => props.device, async (d) => {
  if (!d) return
  try {
    const r = await fetch(`/api/v1/experiment/plans?process_type=${d.device_type}&limit=10`)
    if (r.ok) availablePlans.value = (await r.json()).filter((p: any) => p.status === 'draft' || p.status === 'ready')
  } catch { /* ignore */ }
}, { immediate: true })

async function assignExperiment() {
  if (!selectedPlanId.value || !props.device) return
  assigning.value = true
  try {
    const r = await fetch(`/api/v1/mock/devices/${props.device.device_id}/experiments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plan_id: selectedPlanId.value }),
    })
    if (r.ok) {
      ElMessage.success('实验已分配')
      currentExp.value = { planId: selectedPlanId.value, progress: 0, done: 0, total: '?', status: '' }
      selectedPlanId.value = null
    }
  } catch {
    ElMessage.error('分配失败')
  } finally {
    assigning.value = false
  }
}
</script>

<style scoped>
.exp-device-info { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; font-weight: 600; }
.exp-section h4 { font-size: 13px; margin: 0 0 10px 0; color: var(--el-text-color-secondary); }
.exp-progress { margin-bottom: 10px; }
.exp-detail { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 6px; }
</style>

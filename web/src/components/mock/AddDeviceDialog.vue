<template>
  <el-dialog v-model="visible" title="添加模拟设备" width="480px" @close="resetForm">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px" size="default">
      <el-form-item label="工艺类型" prop="device_type">
        <el-select v-model="form.device_type" placeholder="选择工艺类型" style="width:100%">
          <el-option v-for="t in deviceTypes" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="设备编号" prop="device_id">
        <el-input v-model="form.device_id" placeholder="如 reflow-oven-005" />
      </el-form-item>
      <el-form-item label="设备名称">
        <el-input v-model="form.name" placeholder="如 回流焊 5号" />
      </el-form-item>
      <el-form-item label="上报间隔(秒)">
        <el-input-number v-model="form.report_interval" :min="5" :max="3600" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">创建</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits(['update:visible', 'created'])

const visible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

const deviceTypes = [
  { label: '回流焊 (reflow-oven)', value: 'reflow-oven' },
  { label: '注塑成型 (injection-molder)', value: 'injection-molder' },
  { label: '固化炉 (oven-curing)', value: 'oven-curing' },
  { label: 'CNC钻孔 (cnc-drill)', value: 'cnc-drill' },
  { label: '涂覆机 (coating-machine)', value: 'coating-machine' },
  { label: '贴片 (pick-and-place)', value: 'pick-and-place' },
  { label: '波峰焊 (wave-solder)', value: 'wave-solder' },
  { label: '3D打印 (3d-printer)', value: '3d-printer' },
  { label: '测试站 (testing-station)', value: 'testing-station' },
  { label: '激光切割 (laser-cutter)', value: 'laser-cutter' },
  { label: 'X-Ray检测 (xray-inspection)', value: 'xray-inspection' },
  { label: '键合 (wire-bonder)', value: 'wire-bonder' },
  { label: '超声清洗 (ultrasonic-cleaner)', value: 'ultrasonic-cleaner' },
]

const formRef = ref()
const submitting = ref(false)
const form = reactive({
  device_type: 'reflow-oven',
  device_id: '',
  name: '',
  report_interval: 60,
})

const rules = {
  device_type: [{ required: true, message: '请选择工艺类型' }],
  device_id: [{ required: true, message: '请输入设备编号' }],
}

function resetForm() {
  form.device_type = 'reflow-oven'
  form.device_id = ''
  form.name = ''
  form.report_interval = 60
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    const r = await fetch('/api/v1/mock/devices', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    })
    if (!r.ok) {
      const err = await r.json()
      ElMessage.error(err.detail || '创建失败')
      return
    }
    ElMessage.success('设备已创建')
    visible.value = false
    emit('created')
  } finally {
    submitting.value = false
  }
}
</script>

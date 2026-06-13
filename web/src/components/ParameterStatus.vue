<template>
  <el-tag :type="tagType" size="small">
    {{ statusText }}
  </el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ status: string }>()

const statusMap: Record<string, { type: string; text: string }> = {
  draft: { type: 'info', text: '草稿' },
  proposed: { type: 'warning', text: '已提议' },
  approved: { type: 'success', text: '已批准' },
  active: { type: 'primary', text: '已激活' },
  rejected: { type: 'danger', text: '已驳回' },
  archived: { type: '', text: '已归档' },
}

const tagType = computed(() => statusMap[props.status]?.type || 'info')
const statusText = computed(() => statusMap[props.status]?.text || props.status)
</script>

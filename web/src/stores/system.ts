import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchStats } from '@/api/stats'

export const useSystemStore = defineStore('system', () => {
  const serviceStatus = ref<'healthy' | 'degraded' | 'down'>('healthy')
  const todayDataCount = ref(0)
  const pendingApprovals = ref(0)
  const totalRecords = ref(0)
  const deviceCount = ref(0)
  const resources = ref({ cpu: 0, memory: 0, disk: 0 })
  const loading = ref(false)

  async function loadStats() {
    loading.value = true
    try {
      const stats = await fetchStats()
      todayDataCount.value = stats.today_data_count
      pendingApprovals.value = stats.pending_approvals
      totalRecords.value = stats.total_records
      deviceCount.value = stats.device_count
      serviceStatus.value = 'healthy'
    } catch {
      serviceStatus.value = 'degraded'
    } finally {
      loading.value = false
    }
  }

  function updateStatus(status: {
    serviceStatus?: 'healthy' | 'degraded' | 'down'
    resources?: { cpu: number; memory: number; disk: number }
  }) {
    if (status.serviceStatus !== undefined) serviceStatus.value = status.serviceStatus
    if (status.resources !== undefined) resources.value = status.resources
  }

  return {
    serviceStatus, todayDataCount, pendingApprovals, totalRecords, deviceCount,
    resources, loading, loadStats, updateStatus,
  }
})

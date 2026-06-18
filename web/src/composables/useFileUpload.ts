import { ref } from 'vue'
import { useSessionStore } from '@/stores/session'

export function useFileUpload() {
  const uploading = ref(false)

  function getCurrentUser(): string {
    const store = useSessionStore()
    return store.currentUser || 'anonymous'
  }

  async function upload(
    file: File,
    callbacks: {
      onSuccess: (datasetId: string, features: string[], targets: string[]) => void
      onError: (msg: string) => void
    },
  ) {
    if (!file.name.match(/\.(xlsx|xls|csv)$/i)) {
      callbacks.onError('仅支持 .xlsx / .xls / .csv 文件')
      return
    }
    uploading.value = true
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch('/api/v1/agent/upload', {
        method: 'POST',
        headers: { 'X-User': getCurrentUser() },
        body: form,
      })
      if (!res.ok) throw new Error('上传失败')
      const data = await res.json()
      callbacks.onSuccess(data.dataset_id, data.fields?.features || [], data.fields?.targets || [])
    } catch (e: any) {
      callbacks.onError('文件上传失败: ' + (e.message || ''))
    } finally {
      uploading.value = false
    }
  }

  return { uploading, upload }
}

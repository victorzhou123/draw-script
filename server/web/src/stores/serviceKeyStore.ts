import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api, type ServiceApiKey } from '@/services/api'

export const useServiceKeyStore = defineStore('serviceKeys', () => {
  const keys = ref<ServiceApiKey[]>([])
  const loading = ref(false)

  async function fetchKeys() {
    loading.value = true
    try {
      keys.value = await api.getServiceKeys()
    } finally {
      loading.value = false
    }
  }

  async function createKey(data: { service_name: string; api_key?: string; base_url?: string }) {
    const k = await api.createServiceKey(data)
    keys.value.push(k)
    return k
  }

  async function updateKey(id: string, data: { service_name?: string; api_key?: string; base_url?: string }) {
    const k = await api.updateServiceKey(id, data)
    const idx = keys.value.findIndex(x => x.id === id)
    if (idx >= 0) keys.value[idx] = k
    return k
  }

  async function deleteKey(id: string) {
    await api.deleteServiceKey(id)
    keys.value = keys.value.filter(x => x.id !== id)
  }

  return { keys, loading, fetchKeys, createKey, updateKey, deleteKey }
})

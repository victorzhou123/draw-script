import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api, type AIModel } from '@/services/api'

export const useModelStore = defineStore('models', () => {
  const models = ref<AIModel[]>([])
  const loading = ref(false)

  const thirdPartyModels = computed(() =>
    models.value.filter(m => m.type === 'third_party')
  )

  const enabledAIModels = computed(() =>
    models.value.filter(m => m.type === 'third_party' && m.enabled)
  )

  async function fetchModels() {
    loading.value = true
    try {
      models.value = await api.getModels()
    } finally {
      loading.value = false
    }
  }

  async function createModel(data: Omit<AIModel, 'id' | 'created_at' | 'updated_at'>) {
    const m = await api.createModel(data)
    models.value.push(m)
    return m
  }

  async function updateModel(id: string, data: Partial<Omit<AIModel, 'id' | 'type' | 'provider' | 'created_at' | 'updated_at'>>) {
    const m = await api.updateModel(id, data)
    const idx = models.value.findIndex(x => x.id === id)
    if (idx >= 0) models.value[idx] = m
    return m
  }

  async function deleteModel(id: string) {
    await api.deleteModel(id)
    models.value = models.value.filter(x => x.id !== id)
  }

  return {
    models,
    loading,
    thirdPartyModels,
    enabledAIModels,
    fetchModels,
    createModel,
    updateModel,
    deleteModel,
  }
})

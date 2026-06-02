import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, type Script } from '@/services/api'

export const useScriptStore = defineStore('script', () => {
  const scripts = ref<Script[]>([])
  const currentScript = ref<Script | null>(null)
  const loading = ref(false)

  async function fetchScripts() {
    loading.value = true
    try {
      scripts.value = await api.getScripts()
    } finally {
      loading.value = false
    }
  }

  async function selectScript(id: string) {
    const script = await api.getScript(id)
    currentScript.value = script
    return script
  }

  async function createScript(name: string, description = '') {
    const script = await api.createScript({ name, description, flow_json: '{"cells":[]}' })
    scripts.value.unshift(script)
    currentScript.value = script
    return script
  }

  async function saveScript(flowJson: object) {
    if (!currentScript.value) return
    const updated = await api.updateScript(currentScript.value.id, {
      flow_json: JSON.stringify(flowJson),
    })
    currentScript.value = updated
    const idx = scripts.value.findIndex(s => s.id === updated.id)
    if (idx !== -1) scripts.value[idx] = updated
  }

  async function deleteScript(id: string) {
    await api.deleteScript(id)
    scripts.value = scripts.value.filter(s => s.id !== id)
    if (currentScript.value?.id === id) currentScript.value = null
  }

  async function renameScript(id: string, name: string) {
    const updated = await api.updateScript(id, { name })
    const idx = scripts.value.findIndex(s => s.id === id)
    if (idx !== -1) scripts.value[idx] = updated
    if (currentScript.value?.id === id) currentScript.value = { ...currentScript.value, name: updated.name }
    return updated
  }

  async function duplicateScript(id: string) {
    const original = scripts.value.find(s => s.id === id)
    if (!original) return
    const copy = await api.createScript({
      name: `${original.name} 的副本`,
      description: original.description,
      flow_json: original.flow_json,
    })
    scripts.value.unshift(copy)
    return copy
  }

  return { scripts, currentScript, loading, fetchScripts, selectScript, createScript, saveScript, deleteScript, duplicateScript, renameScript }
})

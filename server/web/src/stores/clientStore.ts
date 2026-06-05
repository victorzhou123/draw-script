import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, type Client } from '@/services/api'

export const useClientStore = defineStore('client', () => {
  const clients = ref<Client[]>([])
  const connectedIds = ref<Set<string>>(new Set())
  const selectedClientId = ref<string | null>(null)

  async function fetchClients() {
    clients.value = await api.getClients()
  }

  function setConnectedIds(ids: string[]) {
    connectedIds.value = new Set(ids)
    for (const c of clients.value) {
      c.status = connectedIds.value.has(c.id) ? 'idle' : 'disconnected'
    }
  }

  function onClientConnected(info: { client_id: string; name: string; platform: string }) {
    connectedIds.value.add(info.client_id)
    const existing = clients.value.find(c => c.id === info.client_id)
    if (existing) {
      existing.status = 'idle'
      existing.last_seen = new Date().toISOString()
    } else {
      clients.value.unshift({
        id: info.client_id,
        name: info.name,
        platform: info.platform,
        status: 'idle',
        last_seen: new Date().toISOString(),
        project_ids: [],
        gpu_enabled: false,
      })
    }
  }

  function onClientDisconnected(clientId: string) {
    connectedIds.value.delete(clientId)
    const c = clients.value.find(c => c.id === clientId)
    if (c) c.status = 'disconnected'
  }

  function onHeartbeat(clientId: string, status: string) {
    const c = clients.value.find(c => c.id === clientId)
    if (c) {
      c.status = status
      c.last_seen = new Date().toISOString()
    }
  }

  function onClientStatus(clientId: string, status: string) {
    const c = clients.value.find(c => c.id === clientId)
    if (c) c.status = status
  }

  async function addToProject(clientId: string, projectId: string) {
    await api.addClientToProject(projectId, clientId)
    const c = clients.value.find(c => c.id === clientId)
    if (c && !c.project_ids.includes(projectId)) c.project_ids.push(projectId)
  }

  async function removeFromProject(clientId: string, projectId: string) {
    await api.removeClientFromProject(projectId, clientId)
    const c = clients.value.find(c => c.id === clientId)
    if (c) c.project_ids = c.project_ids.filter(id => id !== projectId)
  }

  async function updateGpu(clientId: string, gpuEnabled: boolean) {
    await api.updateClientGpu(clientId, gpuEnabled)
    const c = clients.value.find(c => c.id === clientId)
    if (c) c.gpu_enabled = gpuEnabled
  }

  return {
    clients,
    connectedIds,
    selectedClientId,
    fetchClients,
    setConnectedIds,
    onClientConnected,
    onClientDisconnected,
    onHeartbeat,
    onClientStatus,
    addToProject,
    removeFromProject,
    updateGpu,
  }
})

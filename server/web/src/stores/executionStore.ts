import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/services/api'

export type ExecutionStatus = 'idle' | 'running' | 'completed' | 'stopped' | 'error'

export interface ClientExecution {
  id: string
  scriptId: string
  status: ExecutionStatus
}

export const useExecutionStore = defineStore('execution', () => {
  // Per-client execution tracking: clientId → execution info
  const clientExecutions = ref<Record<string, ClientExecution>>({})

  // Per-client execution logs: clientId → log lines
  const clientLogs = ref<Record<string, string[]>>({})

  // Watch node snapshots: nodeId → clientId → snapshot
  const watchSnapshots = ref<Record<string, Record<string, Record<string, unknown>>>>({})

  // Currently highlighted node in graph editor
  const activeNodeId = ref<string | null>(null)

  function isRunning(clientId: string): boolean {
    return clientExecutions.value[clientId]?.status === 'running'
  }

  function anyRunning(): boolean {
    return Object.values(clientExecutions.value).some(e => e.status === 'running')
  }

  async function runOnClient(scriptId: string, clientId: string): Promise<void> {
    const exec = await api.runScript(scriptId, clientId)
    clientExecutions.value[clientId] = { id: exec.id, scriptId, status: 'running' }
  }

  async function stopOnClient(clientId: string): Promise<void> {
    const ce = clientExecutions.value[clientId]
    if (!ce || ce.status !== 'running') return
    await api.stopScript(ce.scriptId, ce.id)
  }

  async function runOnProject(scriptId: string, clientIds: string[]): Promise<void> {
    await Promise.allSettled(clientIds.map(id => runOnClient(scriptId, id)))
  }

  async function stopOnProject(clientIds: string[]): Promise<void> {
    await Promise.allSettled(clientIds.filter(isRunning).map(id => stopOnClient(id)))
  }

  function logsFor(clientId: string): string[] {
    return clientLogs.value[clientId] ?? []
  }

  function addLog(message: string, clientId?: string) {
    const key = clientId || '__system__'
    if (!clientLogs.value[key]) clientLogs.value[key] = []
    clientLogs.value[key].push(message)
    if (clientLogs.value[key].length > 500) clientLogs.value[key].shift()
  }

  function clearLogs(clientId?: string) {
    if (clientId) {
      clientLogs.value[clientId] = []
    } else {
      clientLogs.value = {}
    }
  }

  function onWatchSnapshot(nodeId: string, clientId: string, snapshot: Record<string, unknown>) {
    if (!watchSnapshots.value[nodeId]) watchSnapshots.value[nodeId] = {}
    watchSnapshots.value[nodeId][clientId] = snapshot
  }

  // WS event handlers
  function onProgress(nodeId: string, nodeStatus: string) {
    activeNodeId.value = nodeStatus === 'running' ? nodeId : null
  }

  function onFinished(executionId: string, clientId: string, finishStatus: string, error: string | null) {
    if (clientId && clientExecutions.value[clientId]?.id === executionId) {
      clientExecutions.value[clientId].status = finishStatus as ExecutionStatus
    } else {
      // Fallback: search by execution id
      for (const [cid, ce] of Object.entries(clientExecutions.value)) {
        if (ce.id === executionId) {
          clientExecutions.value[cid].status = finishStatus as ExecutionStatus
          break
        }
      }
    }
    activeNodeId.value = null
    if (error) addLog(`[ERROR] ${error}`, clientId)
  }

  return {
    clientExecutions, clientLogs, activeNodeId, watchSnapshots,
    isRunning, anyRunning,
    runOnClient, stopOnClient, runOnProject, stopOnProject,
    logsFor, addLog, clearLogs, onProgress, onFinished, onWatchSnapshot,
  }
})

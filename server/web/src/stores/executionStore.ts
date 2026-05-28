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

  // Shared log across all executions
  const logs = ref<string[]>([])

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

  function addLog(message: string) {
    logs.value.push(message)
    if (logs.value.length > 500) logs.value.shift()
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
    if (error) addLog(`[ERROR] ${error}`)
  }

  return {
    clientExecutions, logs, activeNodeId,
    isRunning, anyRunning,
    runOnClient, stopOnClient, runOnProject, stopOnProject,
    addLog, onProgress, onFinished,
  }
})

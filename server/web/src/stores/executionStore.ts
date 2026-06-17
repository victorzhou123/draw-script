import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
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

  // nodeId → Set of clientIds currently executing that node
  const activeNodeClients = ref(new Map<string, Set<string>>())
  // Derived set of active node IDs for consumers (BaseNode, GraphEditor)
  const activeNodeIds = computed(() => new Set(activeNodeClients.value.keys()))

  // ── Per-node status/action/log (scoped to a script's bound client, latest run only) ──
  // nodeId → terminal status, drives the ✓/✗ corner badge
  const nodeStatus = ref<Record<string, 'done' | 'error'>>({})
  // nodeId → human-readable "what this node did" lines (level=action)
  const nodeActions = ref<Record<string, string[]>>({})
  // nodeId → error/log lines (level=error)
  const nodeLogs = ref<Record<string, string[]>>({})
  // nodeId → ctx.variables snapshot before/after execution
  const nodeContextBefore = ref<Record<string, Record<string, any>>>({})
  const nodeContextAfter = ref<Record<string, Record<string, any>>>({})
  // Accumulated ctx.variables from the last debug run — used as initial vars for next 「执行」
  const debugAccumulatedContext = ref<Record<string, any>>({})
  const _currentDebugExecId = ref<string | null>(null)

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
    if (ce && ce.status === 'running') {
      await api.stopScript(ce.scriptId, ce.id)
    } else {
      // Execution started outside this session — stop by client_id
      await api.stopClient(clientId)
    }
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

  function clearNodeStatus() {
    nodeStatus.value = {}
    nodeActions.value = {}
    nodeLogs.value = {}
    nodeContextBefore.value = {}
    nodeContextAfter.value = {}
  }

  function onNodeProgress(nodeId: string, status: string) {
    if (status === 'done' || status === 'error') {
      nodeStatus.value[nodeId] = status
    }
  }

  function onNodeLog(nodeId: string, level: string, message: string) {
    const bucket = level === 'error' ? nodeLogs.value : nodeActions.value
    if (!bucket[nodeId]) bucket[nodeId] = []
    bucket[nodeId].push(message)
  }

  function nodeActionsFor(nodeId: string): string[] {
    return nodeActions.value[nodeId] ?? []
  }

  function nodeLogsFor(nodeId: string): string[] {
    return nodeLogs.value[nodeId] ?? []
  }

  function onNodeContext(nodeId: string, phase: string, variables: Record<string, any>, executionId?: string) {
    if (phase === 'before') {
      nodeContextBefore.value = { ...nodeContextBefore.value, [nodeId]: variables }
    } else {
      nodeContextAfter.value = { ...nodeContextAfter.value, [nodeId]: variables }
      if (executionId && executionId === _currentDebugExecId.value) {
        debugAccumulatedContext.value = { ...variables }
      }
    }
  }

  function setDebugExecution(executionId: string) {
    _currentDebugExecId.value = executionId
  }

  function clearNodeStatusFor(nodeId: string) {
    const dropKey = (rec: Record<string, any>) => {
      if (rec[nodeId] === undefined) return rec
      const next = { ...rec }
      delete next[nodeId]
      return next
    }
    nodeStatus.value = dropKey(nodeStatus.value) as Record<string, 'done' | 'error'>
    nodeActions.value = dropKey(nodeActions.value) as Record<string, string[]>
    nodeLogs.value = dropKey(nodeLogs.value) as Record<string, string[]>
    nodeContextBefore.value = dropKey(nodeContextBefore.value)
    nodeContextAfter.value = dropKey(nodeContextAfter.value)
  }

  function nodeContextBeforeFor(nodeId: string): Record<string, any> | null {
    return nodeContextBefore.value[nodeId] ?? null
  }

  function nodeContextAfterFor(nodeId: string): Record<string, any> | null {
    return nodeContextAfter.value[nodeId] ?? null
  }

  // WS event handlers
  function onProgress(nodeId: string, nodeStatus: string, clientId: string) {
    const next = new Map(activeNodeClients.value)
    if (nodeStatus === 'running') {
      if (!next.has(nodeId)) next.set(nodeId, new Set())
      next.get(nodeId)!.add(clientId)
    } else {
      const clients = next.get(nodeId)
      if (clients) {
        clients.delete(clientId)
        if (clients.size === 0) next.delete(nodeId)
      }
    }
    activeNodeClients.value = next
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
    // Remove finished client from all active nodes
    const next = new Map(activeNodeClients.value)
    for (const [nodeId, clients] of next) {
      clients.delete(clientId)
      if (clients.size === 0) next.delete(nodeId)
    }
    activeNodeClients.value = next
    if (error) addLog(`[ERROR] ${error}`, clientId)
  }

  return {
    clientExecutions, clientLogs, activeNodeIds, activeNodeClients,
    nodeStatus, nodeActions, nodeLogs, nodeContextBefore, nodeContextAfter,
    debugAccumulatedContext,
    isRunning, anyRunning,
    runOnClient, stopOnClient, runOnProject, stopOnProject,
    logsFor, addLog, clearLogs, onProgress, onFinished,
    clearNodeStatus, clearNodeStatusFor, onNodeProgress, onNodeLog, nodeActionsFor, nodeLogsFor,
    onNodeContext, nodeContextBeforeFor, nodeContextAfterFor,
    setDebugExecution,
  }
})

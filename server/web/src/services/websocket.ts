import { useClientStore } from '@/stores/clientStore'
import { useExecutionStore } from '@/stores/executionStore'
import { useScriptStore } from '@/stores/scriptStore'

function isBoundClient(clientId: string | undefined): boolean {
  if (!clientId) return false
  const scriptStore = useScriptStore()
  return !!scriptStore.currentScript?.default_client_id && scriptStore.currentScript.default_client_id === clientId
}

class UIWebSocket {
  private ws: WebSocket | null = null
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private reconnectDelay = 2000

  connect() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${location.host}/ws/ui`
    this.ws = new WebSocket(url)

    this.ws.onopen = () => {
      console.log('[WS] UI WebSocket connected')
      this.reconnectDelay = 2000
    }

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        this.dispatch(msg)
      } catch (e) {
        console.warn('[WS] Invalid JSON:', event.data)
      }
    }

    this.ws.onclose = () => {
      console.log('[WS] UI WebSocket disconnected, reconnecting...')
      this.scheduleReconnect()
    }

    this.ws.onerror = () => {
      this.ws?.close()
    }
  }

  private dispatch(msg: Record<string, unknown>) {
    const clientStore = useClientStore()
    const executionStore = useExecutionStore()

    switch (msg.type) {
      case 'init':
        clientStore.setConnectedIds(msg.connected_clients as string[])
        break
      case 'client_connected':
        clientStore.onClientConnected(msg as any)
        break
      case 'client_disconnected':
        clientStore.onClientDisconnected(msg.client_id as string)
        break
      case 'client_heartbeat':
        clientStore.onHeartbeat(msg.client_id as string, msg.status as string)
        break
      case 'client_status':
        clientStore.onClientStatus(msg.client_id as string, msg.status as string)
        break
      case 'execution_started': {
        const scriptStore = useScriptStore()
        const startedScriptId = msg.script_id as string | undefined
        const startedClientId = msg.client_id as string | undefined
        const isDebug = !!msg.debug
        const debugNodeId = msg.debug_node_id as string | undefined
        const executionId = msg.execution_id as string
        if (isBoundClient(startedClientId) && startedScriptId === scriptStore.currentScript?.id) {
          if (isDebug && debugNodeId) {
            // 「执行」single node: only wipe that node's status, leave others intact
            executionStore.clearNodeStatusFor(debugNodeId)
            executionStore.setDebugExecution(executionId)
          } else if (isDebug) {
            // 「执行到此」: fresh run from Start — clear all, still track as debug exec
            executionStore.clearNodeStatus()
            executionStore.setDebugExecution(executionId)
          } else {
            executionStore.clearNodeStatus()
          }
        }
        break
      }
      case 'execution_progress':
        if (isBoundClient(msg.client_id as string | undefined)) {
          executionStore.onProgress(msg.node_id as string, msg.status as string, msg.client_id as string)
          executionStore.onNodeProgress(msg.node_id as string, msg.status as string)
        }
        break
      case 'execution_log':
        executionStore.addLog(msg.message as string, msg.client_id as string | undefined)
        if (isBoundClient(msg.client_id as string | undefined) && msg.node_id) {
          executionStore.onNodeLog(msg.node_id as string, msg.level as string, msg.message as string)
        }
        break
      case 'execution_finished':
        executionStore.onFinished(
          msg.execution_id as string,
          msg.client_id as string,
          msg.status as string,
          msg.error as string | null,
        )
        break
      case 'execution_context':
        if (isBoundClient(msg.client_id as string | undefined) && msg.node_id) {
          executionStore.onNodeContext(
            msg.node_id as string,
            msg.phase as string,
            msg.variables as Record<string, any>,
            msg.execution_id as string,
          )
        }
        break
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    this.reconnectTimer = setTimeout(() => {
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000)
      this.connect()
    }, this.reconnectDelay)
  }

  disconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    this.ws?.close()
  }
}

export const uiWS = new UIWebSocket()

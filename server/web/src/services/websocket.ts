import { useClientStore } from '@/stores/clientStore'
import { useExecutionStore } from '@/stores/executionStore'

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
      case 'execution_started':
        // Per-client tracking is done in runOnClient; no store update needed here
        break
      case 'execution_progress':
        executionStore.onProgress(msg.node_id as string, msg.status as string)
        break
      case 'execution_log':
        executionStore.addLog(msg.message as string)
        break
      case 'execution_finished':
        executionStore.onFinished(
          msg.execution_id as string,
          msg.client_id as string,
          msg.status as string,
          msg.error as string | null,
        )
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

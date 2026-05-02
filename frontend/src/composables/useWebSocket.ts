import { ref, onUnmounted } from 'vue'

export interface WsMessage {
  type: string
  data?: any
}

export function useWebSocket() {
  const connected = ref(false)
  const lastMessage = ref<WsMessage | null>(null)

  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let reconnectDelay = 1000 // start at 1s
  const maxReconnectDelay = 30000 // max 30s
  let shouldReconnect = true

  function connect() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return
    }

    shouldReconnect = true
    const protocol = import.meta.env.DEV ? 'ws' : 'wss'
    const url = `${protocol}://${window.location.host}/ws`

    try {
      ws = new WebSocket(url)

      ws.onopen = () => {
        connected.value = true
        reconnectDelay = 1000 // reset backoff on successful connection
      }

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data) as WsMessage
          lastMessage.value = msg
        } catch {
          // ignore malformed messages
        }
      }

      ws.onclose = () => {
        connected.value = false
        ws = null
        if (shouldReconnect) {
          scheduleReconnect()
        }
      }

      ws.onerror = () => {
        // onclose will fire after onerror, so reconnect is handled there
        connected.value = false
      }
    } catch {
      // connection failed, schedule reconnect
      if (shouldReconnect) {
        scheduleReconnect()
      }
    }
  }

  function scheduleReconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    reconnectTimer = setTimeout(() => {
      reconnectDelay = Math.min(reconnectDelay * 2, maxReconnectDelay)
      connect()
    }, reconnectDelay)
  }

  function disconnect() {
    shouldReconnect = false
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws) {
      ws.close()
      ws = null
    }
    connected.value = false
  }

  onUnmounted(() => {
    disconnect()
  })

  return { connected, lastMessage, connect, disconnect }
}

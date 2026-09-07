import { ref } from 'vue'

export interface WSMessage {
  type: string
  data: Record<string, any>
}

const MAX_MESSAGES = 500

export function useWebSocket(testId: string) {
  const ws = ref<WebSocket | null>(null)
  const connected = ref(false)
  const messages = ref<WSMessage[]>([])

  const connect = () => {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${location.host}/ws/v1/tests/${testId}`

    ws.value = new WebSocket(url)

    ws.value.onopen = () => {
      connected.value = true
      ws.value?.send(JSON.stringify({
        type: 'subscribe',
        topics: ['log', 'progress', 'interaction', 'status'],
      }))
    }

    ws.value.onmessage = (event) => {
      const msg: WSMessage = JSON.parse(event.data)
      messages.value.push(msg)
      if (messages.value.length > MAX_MESSAGES) {
        messages.value.shift()
      }
    }

    ws.value.onclose = () => {
      connected.value = false
    }

    ws.value.onerror = (err) => {
      console.error('WebSocket error:', err)
      connected.value = false
    }
  }

  const disconnect = () => {
    ws.value?.close()
    ws.value = null
    connected.value = false
  }

  const send = (type: string, data: Record<string, any> = {}) => {
    ws.value?.send(JSON.stringify({ type, ...data }))
  }

  return { ws, connected, messages, connect, disconnect, send }
}

import { useEffect, useRef, useCallback } from 'react'
import { useFlowTraceStore } from '../stores/flowtraceStore'

/**
 * Custom hook that manages a WebSocket connection with:
 *  - Automatic reconnect (exponential back-off, max 30 s)
 *  - Clean disconnect on unmount
 *  - Exposes connection status from global store
 */
export function useWebSocket(url = 'ws://localhost:8000/ws/dashboard') {
  const connectWebSocket = useFlowTraceStore((s) => s.connectWebSocket)
  const disconnectWebSocket = useFlowTraceStore((s) => s.disconnectWebSocket)
  const wsStatus = useFlowTraceStore((s) => s.wsStatus)
  const hasConnected = useRef(false)

  const connect = useCallback(() => {
    connectWebSocket(url)
    hasConnected.current = true
  }, [connectWebSocket, url])

  useEffect(() => {
    connect()
    return () => {
      if (hasConnected.current) disconnectWebSocket()
    }
  }, [connect, disconnectWebSocket])

  return { wsStatus, reconnect: connect }
}

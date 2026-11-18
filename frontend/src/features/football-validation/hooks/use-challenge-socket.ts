import { useCallback, useEffect, useRef, useState } from "react"
import { useAuthStore } from "@/stores/auth-store"
import type { ChallengeSegment } from "../state/football-session-machine"

export type ClientAntiFraudEvent =
  | "tab_hidden"
  | "focus_lost"
  | "fullscreen_exit"

export interface ChallengeSocketMessage {
  type: "command" | "status" | "progress" | "result_ready" | "pong"
  session_id: string
  data: Record<string, unknown>
}

export function useChallengeSocket(wsPath: string | null) {
  const [isConnected, setIsConnected] = useState(false)
  const [activeCommand, setActiveCommand] = useState<ChallengeSegment | null>(
    null
  )
  const [lastStatus, setLastStatus] = useState<Record<string, unknown> | null>(
    null
  )
  const wsRef = useRef<WebSocket | null>(null)
  const startTimeRef = useRef<number>(0)

  const sendClientEvent = useCallback((event: ClientAntiFraudEvent) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
    const elapsedMs = Math.max(0, Date.now() - startTimeRef.current)
    wsRef.current.send(
      JSON.stringify({
        type: "client_event",
        event,
        timestamp_ms: elapsedMs,
      })
    )
  }, [])

  const sendPing = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
    const elapsedMs = Math.max(0, Date.now() - startTimeRef.current)
    wsRef.current.send(
      JSON.stringify({
        type: "ping",
        timestamp_ms: elapsedMs,
      })
    )
  }, [])

  useEffect(() => {
    if (!wsPath || typeof WebSocket === "undefined") return

    const token = useAuthStore.getState().token
    const apiBase =
      import.meta.env.VITE_API_URL || "http://localhost:8000/api"
    const wsOrigin = apiBase
      .replace(/\/api\/?$/, "")
      .replace(/^http/, "ws")
    const fullUrl = `${wsOrigin}${wsPath}${token ? `?token=${encodeURIComponent(token)}` : ""}`

    startTimeRef.current = Date.now()
    const socket = new WebSocket(fullUrl)
    wsRef.current = socket

    socket.onopen = () => {
      setIsConnected(true)
    }

    socket.onmessage = (evt: MessageEvent) => {
      try {
        const parsed = JSON.parse(String(evt.data)) as ChallengeSocketMessage
        if (parsed.type === "command") {
          setActiveCommand({
            indice: Number(parsed.data.indice ?? 0),
            tipo: (parsed.data.tipo as ChallengeSegment["tipo"]) ?? "LOW",
            inicio_servidor_ms: Number(parsed.data.inicio_servidor_ms ?? 0),
            duracion_ms: Number(parsed.data.duracion_ms ?? 8000),
          })
        } else if (parsed.type === "status") {
          setLastStatus(parsed.data)
        }
      } catch {
        // Ignore malformed messages
      }
    }

    socket.onclose = () => {
      setIsConnected(false)
    }

    return () => {
      socket.close()
      wsRef.current = null
    }
  }, [wsPath])

  return {
    isConnected,
    activeCommand,
    lastStatus,
    sendClientEvent,
    sendPing,
  }
}

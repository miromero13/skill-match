import { apiClient } from "@/services/api-client"
import type { WebSocketTicketData } from "@/types/realtime-notification"

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api"
const requestOptions = { showToastOnError: true, showToastOnSuccess: false }

export function getRealtimeApiUrl() {
  return API_URL
}

export function getWebSocketTicket() {
  return apiClient.get<WebSocketTicketData>(
    "/notifications/ws-token",
    requestOptions
  )
}

export function buildWebSocketUrl(
  apiUrl: string,
  data: WebSocketTicketData
): string {
  if (
    !data ||
    typeof data.ticket !== "string" ||
    !data.ticket.trim() ||
    data.websocket_path !== "/ws/notifications" ||
    !Number.isSafeInteger(data.expires_in) ||
    data.expires_in < 5 ||
    data.expires_in > 120
  ) {
    throw new Error("El backend devolvió un ticket WebSocket inválido.")
  }
  const url = new URL(apiUrl)
  if (url.protocol !== "http:" && url.protocol !== "https:")
    throw new Error("El protocolo de la API no permite WebSocket seguro.")
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:"
  url.pathname = data.websocket_path
  url.search = new URLSearchParams({ ticket: data.ticket }).toString()
  url.hash = ""
  return url.toString()
}

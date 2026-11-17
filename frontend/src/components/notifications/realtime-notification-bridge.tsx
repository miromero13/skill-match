import { useNotificationWebSocket } from "@/hooks/use-notification-websocket"

/** Keeps one realtime lifecycle above every authenticated route/layout. */
export function RealtimeNotificationBridge() {
  useNotificationWebSocket()
  return null
}

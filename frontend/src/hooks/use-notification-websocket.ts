import { useEffect } from "react"
import { useRealtimeNotificationStore } from "@/stores/realtime-notification-store"

export function useNotificationWebSocket() {
  const connect = useRealtimeNotificationStore((state) => state.connect)
  const disconnect = useRealtimeNotificationStore((state) => state.disconnect)

  useEffect(() => {
    void connect()
    return disconnect
  }, [connect, disconnect])
}

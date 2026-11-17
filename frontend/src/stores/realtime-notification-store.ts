import { create } from "zustand"
import { toast } from "sonner"
import {
  buildWebSocketUrl,
  getWebSocketTicket,
} from "@/services/realtime-notification-service"
import { getAuthSessionVersion, useAuthStore } from "@/stores/auth-store"
import { useNotificationStore } from "@/stores/notification-store"
import { notificationCategories } from "@/types/notification"
import {
  realtimeNotificationTypes,
  type RealtimeConnectionStatus,
  type RealtimeNotificationEvent,
} from "@/types/realtime-notification"

interface RealtimeNotificationState {
  status: RealtimeConnectionStatus
  attempt: number
  lastError: string | null
  connect: () => Promise<boolean>
  disconnect: () => void
  reset: () => void
}

const MAX_SEEN_IDS = 1_000
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api"
let socket: WebSocket | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let generation = 0
let intentionalClose = false
const seenIds = new Set<string>()

function authenticated() {
  const auth = useAuthStore.getState()
  return Boolean(auth.isAuthenticated && auth.token && auth.user?.id)
}

function clearTimer() {
  if (reconnectTimer !== null) clearTimeout(reconnectTimer)
  reconnectTimer = null
}

function remember(id: string) {
  if (seenIds.has(id)) return false
  seenIds.add(id)
  if (seenIds.size > MAX_SEEN_IDS) {
    const oldest = seenIds.values().next().value
    if (typeof oldest === "string") seenIds.delete(oldest)
  }
  return true
}

function isRealtimeEvent(value: unknown): value is RealtimeNotificationEvent {
  if (!value || typeof value !== "object") return false
  const event = value as Record<string, unknown>
  if (
    event.event !== "notification.created" ||
    typeof event.message !== "string" ||
    !event.data ||
    typeof event.data !== "object"
  )
    return false
  const data = event.data as Record<string, unknown>
  return (
    typeof data.id === "string" &&
    realtimeNotificationTypes.includes(
      data.type as (typeof realtimeNotificationTypes)[number]
    ) &&
    notificationCategories.includes(
      data.category as (typeof notificationCategories)[number]
    ) &&
    typeof data.title === "string" &&
    typeof data.message === "string" &&
    event.message === data.message &&
    typeof data.created_at === "string" &&
    (data.read_at === null || typeof data.read_at === "string")
  )
}

function reconcileNotifications() {
  const notifications = useNotificationStore.getState()
  useNotificationStore.setState((state) => ({
    realtimeRevision: state.realtimeRevision + 1,
  }))
  void Promise.all([notifications.loadUnread(), notifications.loadList()])
}

function scheduleReconnect(epoch: number) {
  if (epoch !== generation || !authenticated()) return
  if (typeof navigator !== "undefined" && !navigator.onLine) {
    useRealtimeNotificationStore.setState({ status: "disconnected" })
    return
  }
  const attempt = useRealtimeNotificationStore.getState().attempt + 1
  const base = Math.min(30_000, 1_000 * 2 ** Math.min(attempt - 1, 5))
  const jitter = Math.floor(Math.random() * Math.min(250, base / 4))
  useRealtimeNotificationStore.setState({ status: "reconnecting", attempt })
  clearTimer()
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null
    if (epoch === generation)
      void useRealtimeNotificationStore.getState().connect()
  }, base + jitter)
}

export const useRealtimeNotificationStore = create<RealtimeNotificationState>(
  (set, get) => ({
    status: "idle",
    attempt: 0,
    lastError: null,
    connect: async () => {
      if (!authenticated()) return false
      if (socket && (socket.readyState === 0 || socket.readyState === 1))
        return true
      clearTimer()
      const epoch = generation
      const sessionVersion = getAuthSessionVersion()
      const ownerId = useAuthStore.getState().user?.id
      set({
        status: get().attempt > 0 ? "reconnecting" : "connecting",
        lastError: null,
      })
      try {
        const response = await getWebSocketTicket()
        if (
          epoch !== generation ||
          sessionVersion !== getAuthSessionVersion() ||
          ownerId !== useAuthStore.getState().user?.id
        )
          return false
        intentionalClose = false
        const current = new WebSocket(buildWebSocketUrl(API_URL, response.data))
        socket = current
        current.onopen = () => {
          if (epoch !== generation || socket !== current) return
          set({ status: "connected", attempt: 0, lastError: null })
          reconcileNotifications()
        }
        current.onmessage = (message) => {
          if (epoch !== generation || socket !== current) return
          try {
            const payload: unknown = JSON.parse(String(message.data))
            if (!isRealtimeEvent(payload) || !remember(payload.data.id)) return
            toast.success(payload.message)
            reconcileNotifications()
          } catch {
            // Invalid server data is ignored; it must not break the live client.
          }
        }
        current.onerror = () => {
          if (epoch === generation && socket === current)
            set({ lastError: "Se perdió la conexión de notificaciones." })
        }
        current.onclose = () => {
          if (socket === current) socket = null
          if (epoch !== generation || intentionalClose) return
          scheduleReconnect(epoch)
        }
        return true
      } catch (error) {
        if (epoch !== generation) return false
        set({
          lastError:
            error instanceof Error
              ? error.message
              : "No se pudo conectar a las notificaciones.",
        })
        scheduleReconnect(epoch)
        return false
      }
    },
    disconnect: () => {
      generation++
      intentionalClose = true
      clearTimer()
      const current = socket
      socket = null
      if (current) current.close(1000, "Sesión finalizada")
      seenIds.clear()
      set({ status: "idle", attempt: 0, lastError: null })
    },
    reset: () => get().disconnect(),
  })
)

let previousAuth = useAuthStore.getState()
useAuthStore.subscribe((current) => {
  const sessionChanged =
    current.isAuthenticated !== previousAuth.isAuthenticated ||
    current.user?.id !== previousAuth.user?.id ||
    current.token !== previousAuth.token
  previousAuth = current
  if (!sessionChanged) return
  useRealtimeNotificationStore.getState().disconnect()
  if (current.isAuthenticated && current.token && current.user?.id)
    void useRealtimeNotificationStore.getState().connect()
})

if (typeof window !== "undefined") {
  window.addEventListener("online", () => {
    if (authenticated()) void useRealtimeNotificationStore.getState().connect()
  })

  window.addEventListener("offline", () => {
    clearTimer()
    useRealtimeNotificationStore.setState({ status: "disconnected" })
  })

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && authenticated())
      void useRealtimeNotificationStore.getState().connect()
  })
}

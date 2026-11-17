import type { NotificationItem, NotificationType } from "@/types/notification"

export const realtimeNotificationTypes = [
  "MATCH_RECEIVED",
  "MATCH_CONFIRMED",
  "SESSION_PROPOSED",
  "POINTS_RECEIVED",
] as const satisfies readonly NotificationType[]

export type RealtimeNotificationType =
  (typeof realtimeNotificationTypes)[number]

export interface WebSocketTicketData {
  ticket: string
  expires_in: number
  websocket_path: "/ws/notifications"
}

export interface RealtimeNotificationItem extends NotificationItem {
  type: RealtimeNotificationType
}

export interface RealtimeNotificationEvent {
  event: "notification.created"
  message: string
  data: RealtimeNotificationItem
}

export type RealtimeControlEvent = { event: "ping" } | { event: "pong" }

export type RealtimeConnectionStatus =
  "idle" | "connecting" | "connected" | "reconnecting" | "disconnected"

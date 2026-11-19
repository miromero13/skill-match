export interface SessionReminderPushPayload {
  type: "SESSION_REMINDER"
  title: string
  body: string
  url?: string
  event_id: string
}

export interface WebPushNotification {
  title: string
  options: NotificationOptions & { renotify: boolean }
}

const SESSIONS_ROUTE = "/app/sessions"

export function resolveWebPushTarget(target?: string): string {
  return target === SESSIONS_ROUTE ? target : SESSIONS_ROUTE
}

export function buildWebPushNotification(
  payload: SessionReminderPushPayload
): WebPushNotification {
  return {
    title: payload.title,
    options: {
      body: payload.body,
      tag: payload.event_id,
      renotify: false,
      data: { url: resolveWebPushTarget(payload.url) },
    },
  }
}

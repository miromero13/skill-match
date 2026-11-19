const SESSIONS_ROUTE = "/app/sessions"

function canonicalTarget(value) {
  return value === SESSIONS_ROUTE ? value : SESSIONS_ROUTE
}

self.addEventListener("push", (event) => {
  let payload = {}
  try {
    payload = event.data ? event.data.json() : {}
  } catch {
    payload = {}
  }
  const title =
    typeof payload.title === "string" && payload.title.trim()
      ? payload.title
      : "Recordatorio de sesión"
  const body = typeof payload.body === "string" ? payload.body : "Tienes una sesión próxima."
  const tag = typeof payload.event_id === "string" ? payload.event_id : "session-reminder"
  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      tag,
      renotify: false,
      data: { url: canonicalTarget(payload.url) },
    })
  )
})

self.addEventListener("notificationclick", (event) => {
  event.notification.close()
  const target = canonicalTarget(event.notification.data?.url)
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        const current = new URL(client.url)
        if (current.origin === self.location.origin && current.pathname === target) {
          return client.focus()
        }
      }
      return self.clients.openWindow(target)
    })
  )
})

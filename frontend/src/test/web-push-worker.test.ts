import { describe, expect, it } from "vitest"

import {
  buildWebPushNotification,
  resolveWebPushTarget,
} from "@/services/web-push-worker"

describe("Web Push service-worker contract", () => {
  it("builds a visible notification tagged by event identity", () => {
    const notification = buildWebPushNotification({
      type: "SESSION_REMINDER",
      title: "Recordatorio de sesión",
      body: "Tu sesión comienza en 1 hora.",
      url: "/app/sessions",
      event_id: "event-one",
    })
    expect(notification.title).toBe("Recordatorio de sesión")
    expect(notification.options).toEqual(
      expect.objectContaining({
        body: "Tu sesión comienza en 1 hora.",
        tag: "event-one",
        renotify: false,
        data: { url: "/app/sessions" },
      })
    )
  })

  it("opens only the canonical internal sessions route", () => {
    expect(resolveWebPushTarget("/app/sessions")).toBe("/app/sessions")
    expect(resolveWebPushTarget("https://malicious.example/steal")).toBe("/app/sessions")
    expect(resolveWebPushTarget("javascript:alert(1)")).toBe("/app/sessions")
    expect(resolveWebPushTarget("/admin/users")).toBe("/app/sessions")
    expect(resolveWebPushTarget(undefined)).toBe("/app/sessions")
  })
})

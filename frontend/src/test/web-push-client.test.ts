import { beforeEach, describe, expect, it, vi } from "vitest"

import { apiClient } from "@/services/api-client"
import {
  getWebPushCapability,
  requestWebPushSubscription,
  revokeWebPushSubscription,
} from "@/services/web-push-service"

vi.mock("@/services/api-client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}))

const pushSubscription = {
  endpoint: "https://push.example.test/send/browser-one",
  unsubscribe: vi.fn(),
  toJSON: () => ({
    endpoint: "https://push.example.test/send/browser-one",
    keys: { p256dh: "public-key", auth: "auth-secret" },
  }),
}
const subscribe = vi.fn()
const getSubscription = vi.fn()
const register = vi.fn()

function installBrowser(permission: NotificationPermission = "default") {
  Object.defineProperty(globalThis, "Notification", {
    configurable: true,
    value: {
      permission,
      requestPermission: vi.fn().mockResolvedValue("granted"),
    },
  })
  Object.defineProperty(navigator, "serviceWorker", {
    configurable: true,
    value: { register },
  })
  register.mockResolvedValue({
    pushManager: { subscribe, getSubscription },
  })
  subscribe.mockResolvedValue(pushSubscription)
  getSubscription.mockResolvedValue(pushSubscription)
}

beforeEach(() => {
  vi.clearAllMocks()
  installBrowser()
  vi.mocked(apiClient.get).mockResolvedValue({
    statuscode: 200,
    message: "Clave recuperada",
    data: { public_key: "BEl6Y2g" },
  })
  vi.mocked(apiClient.post).mockResolvedValue({
    statuscode: 201,
    message: "Suscripción registrada",
    data: { id: "subscription-one", device_label: "Chrome desktop", is_active: true },
  })
  vi.mocked(apiClient.delete).mockResolvedValue({
    statuscode: 200,
    message: "Suscripción revocada",
    data: null,
  })
})

describe("Web Push browser contract", () => {
  it("reports unsupported without requesting permission", async () => {
    Object.defineProperty(navigator, "serviceWorker", {
      configurable: true,
      value: undefined,
    })
    const capability = await getWebPushCapability()
    expect(capability.status).toBe("UNSUPPORTED")
    expect(Notification.requestPermission).not.toHaveBeenCalled()
  })

  it("requests permission only after the explicit subscription action", async () => {
    expect(Notification.requestPermission).not.toHaveBeenCalled()
    await getWebPushCapability()
    expect(Notification.requestPermission).not.toHaveBeenCalled()

    const result = await requestWebPushSubscription("Chrome desktop")

    expect(Notification.requestPermission).toHaveBeenCalledOnce()
    expect(register).toHaveBeenCalledWith("/service-worker.js", { scope: "/" })
    expect(apiClient.get).toHaveBeenCalledWith(
      "/notifications/push/public-key",
      expect.any(Object)
    )
    expect(subscribe).toHaveBeenCalledWith({
      userVisibleOnly: true,
      applicationServerKey: expect.any(Uint8Array),
    })
    expect(apiClient.post).toHaveBeenCalledWith(
      "/notifications/push/subscriptions",
      expect.objectContaining({
        endpoint: pushSubscription.endpoint,
        keys: { p256dh: "public-key", auth: "auth-secret" },
        device_label: "Chrome desktop",
      }),
      expect.any(Object)
    )
    expect(result.status).toBe("SUBSCRIBED")
  })

  it("does not register or call the API when permission is denied", async () => {
    installBrowser("denied")
    const result = await requestWebPushSubscription("Blocked browser")
    expect(result.status).toBe("DENIED")
    expect(Notification.requestPermission).not.toHaveBeenCalled()
    expect(register).not.toHaveBeenCalled()
    expect(apiClient.post).not.toHaveBeenCalled()
  })

  it("revokes backend identity and browser subscription", async () => {
    pushSubscription.unsubscribe.mockResolvedValue(true)
    const result = await revokeWebPushSubscription("subscription-one")
    expect(apiClient.delete).toHaveBeenCalledWith(
      "/notifications/push/subscriptions/subscription-one",
      expect.any(Object)
    )
    expect(pushSubscription.unsubscribe).toHaveBeenCalledOnce()
    expect(result.status).toBe("UNSUBSCRIBED")
  })
})

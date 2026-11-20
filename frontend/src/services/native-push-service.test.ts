import { beforeEach, describe, expect, it, vi } from "vitest"

const cap = vi.hoisted(() => ({
  isNativePlatform: vi.fn(() => true),
  getPlatform: vi.fn(() => "android"),
}))

const push = vi.hoisted(() => ({
  checkPermissions: vi.fn(),
  requestPermissions: vi.fn(),
  createChannel: vi.fn(),
  addListener: vi.fn(),
  register: vi.fn(),
}))

vi.mock("@capacitor/core", () => ({ Capacitor: cap }))
vi.mock("@capacitor/push-notifications", () => ({ PushNotifications: push }))
vi.mock("sonner", () => ({ toast: { info: vi.fn() } }))

beforeEach(() => {
  vi.resetModules()
  vi.clearAllMocks()
  cap.isNativePlatform.mockReturnValue(true)
  push.checkPermissions.mockResolvedValue({ receive: "granted" })
  push.requestPermissions.mockResolvedValue({ receive: "granted" })
  push.addListener.mockResolvedValue({ remove: vi.fn() })
  push.register.mockResolvedValue(undefined)
})

describe("native push service", () => {
  it("safely skips registration on web / non-native platforms", async () => {
    cap.isNativePlatform.mockReturnValue(false)
    const { initializeNativePushNotifications } = await import("./native-push-service")
    await initializeNativePushNotifications()
    expect(push.checkPermissions).not.toHaveBeenCalled()
    expect(push.register).not.toHaveBeenCalled()
  })

  it("requests permissions when status is prompt", async () => {
    push.checkPermissions.mockResolvedValue({ receive: "prompt" })
    push.requestPermissions.mockResolvedValue({ receive: "granted" })
    const { initializeNativePushNotifications } = await import("./native-push-service")
    await initializeNativePushNotifications()
    expect(push.requestPermissions).toHaveBeenCalled()
    expect(push.register).toHaveBeenCalled()
  })

  it("does not register if permission is denied", async () => {
    push.checkPermissions.mockResolvedValue({ receive: "denied" })
    const { initializeNativePushNotifications } = await import("./native-push-service")
    await initializeNativePushNotifications()
    expect(push.register).not.toHaveBeenCalled()
  })

  it("registers listeners and initializes push when granted", async () => {
    const { initializeNativePushNotifications } = await import("./native-push-service")
    const onNotificationTap = vi.fn()
    await initializeNativePushNotifications(onNotificationTap)
    expect(push.createChannel).toHaveBeenCalledWith(expect.objectContaining({
      id: "skillmatch_notifications",
      importance: 5,
    }))
    expect(push.addListener).toHaveBeenCalledWith("registration", expect.any(Function))
    expect(push.addListener).toHaveBeenCalledWith("registrationError", expect.any(Function))
    expect(push.addListener).toHaveBeenCalledWith("pushNotificationReceived", expect.any(Function))
    expect(push.addListener).toHaveBeenCalledWith("pushNotificationActionPerformed", expect.any(Function))
    expect(push.register).toHaveBeenCalled()
  })
})

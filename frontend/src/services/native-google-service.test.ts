import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const native = vi.hoisted(() => ({
  isNativePlatform: vi.fn(() => true), getPlatform: vi.fn(() => "android"),
  initialize: vi.fn(), login: vi.fn(),
}))
vi.mock("@capacitor/core", () => ({ Capacitor: native }))
vi.mock("@capgo/capacitor-social-login", () => ({ SocialLogin: native }))
beforeEach(() => {
  vi.resetModules(); vi.clearAllMocks()
  native.getPlatform.mockReturnValue("android")
  native.initialize.mockResolvedValue(undefined)
  native.login.mockResolvedValue({ provider: "google", result: { idToken: "native-google-credential" } })
  vi.stubEnv("VITE_GOOGLE_CLIENT_ID", "web-client.apps.googleusercontent.com")
  vi.stubEnv("VITE_GOOGLE_IOS_CLIENT_ID", "ios-client.apps.googleusercontent.com")
})
afterEach(() => vi.unstubAllEnvs())

describe("native Google identity", () => {
  it("requests only Google identity and returns its token for backend verification", async () => {
    const { getNativeGoogleCredential } = await import("./native-google-service")
    expect(await getNativeGoogleCredential()).toBe("native-google-credential")
    expect(native.initialize).toHaveBeenCalledWith({ google: {
      webClientId: "web-client.apps.googleusercontent.com", mode: "online", skipAuthOnlyAuthorizationAfterSignIn: true,
    } })
    expect(native.login).toHaveBeenCalledWith({ provider: "google", options: {} })
  })
  it("uses the iOS client and the same server audience as the web/backend client", async () => {
    native.getPlatform.mockReturnValue("ios")
    const { getNativeGoogleCredential } = await import("./native-google-service")
    await getNativeGoogleCredential()
    expect(native.initialize).toHaveBeenCalledWith({ google: expect.objectContaining({
      iOSClientId: "ios-client.apps.googleusercontent.com", iOSServerClientId: "web-client.apps.googleusercontent.com",
    }) })
  })
  it("fails closed before contacting the SDK when the native iOS client is missing", async () => {
    native.getPlatform.mockReturnValue("ios")
    vi.stubEnv("VITE_GOOGLE_IOS_CLIENT_ID", "")
    const { getNativeGoogleCredential } = await import("./native-google-service")
    await expect(getNativeGoogleCredential()).rejects.toThrow("El acceso con Google no está configurado.")
    expect(native.initialize).not.toHaveBeenCalled()
    expect(native.login).not.toHaveBeenCalled()
  })
  it("rejects SDK success without an ID token instead of trusting a client profile", async () => {
    native.login.mockResolvedValue({ provider: "google", result: { idToken: null, profile: { email: "untrusted@example.com" } } })
    const { getNativeGoogleCredential } = await import("./native-google-service")
    await expect(getNativeGoogleCredential()).rejects.toThrow("Google no devolvió una credencial válida.")
  })
})

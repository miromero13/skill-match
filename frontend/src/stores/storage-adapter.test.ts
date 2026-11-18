import { beforeEach, expect, it, vi } from "vitest"
import { Capacitor } from "@capacitor/core"
import { Preferences } from "@capacitor/preferences"
import { SecureStorage } from "@aparajita/capacitor-secure-storage"
import { hybridAuthStorage } from "./storage-adapter"

vi.mock("@capacitor/core", () => ({ Capacitor: { isNativePlatform: vi.fn(() => true) } }))
vi.mock("@capacitor/preferences", () => ({ Preferences: { get: vi.fn(), set: vi.fn(), remove: vi.fn() } }))
vi.mock("@aparajita/capacitor-secure-storage", () => ({
  SecureStorage: { get: vi.fn(), set: vi.fn(), remove: vi.fn() },
  KeychainAccess: { whenUnlockedThisDeviceOnly: 1 },
}))

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(Capacitor.isNativePlatform).mockReturnValue(true)
  vi.mocked(SecureStorage.get).mockResolvedValue(null)
  vi.mocked(SecureStorage.set).mockResolvedValue()
  vi.mocked(SecureStorage.remove).mockResolvedValue(true)
  vi.mocked(Preferences.get).mockResolvedValue({ value: null })
  vi.mocked(Preferences.remove).mockResolvedValue()
  localStorage.clear()
})

it("writes native credentials only to the device-bound secure store", async () => {
  await hybridAuthStorage.setItem("auth", "session-json")
  expect(SecureStorage.set).toHaveBeenCalledWith("auth", "session-json", false, false, 1)
  expect(Preferences.set).not.toHaveBeenCalled()
  expect(localStorage.getItem("auth")).toBeNull()
})

it("moves an existing native session only after its encrypted copy is stored", async () => {
  vi.mocked(Preferences.get).mockResolvedValue({ value: "legacy-session" })
  expect(await hybridAuthStorage.getItem("auth")).toBe("legacy-session")
  expect(SecureStorage.set).toHaveBeenCalledWith("auth", "legacy-session", false, false, 1)
  expect(Preferences.remove).toHaveBeenCalledWith({ key: "auth" })
  expect(vi.mocked(SecureStorage.set).mock.invocationCallOrder[0]).toBeLessThan(vi.mocked(Preferences.remove).mock.invocationCallOrder[0])
})

it("does not delete a legacy session or downgrade to plaintext when secure storage fails", async () => {
  vi.mocked(Preferences.get).mockResolvedValue({ value: "legacy-session" })
  vi.mocked(SecureStorage.set).mockRejectedValue(new Error("device locked"))
  await expect(hybridAuthStorage.getItem("auth")).rejects.toThrow("device locked")
  expect(Preferences.remove).not.toHaveBeenCalled()
  expect(Preferences.set).not.toHaveBeenCalled()
})

it("keeps a delayed login write ahead of the logout write", async () => {
  let finish!: () => void
  vi.mocked(SecureStorage.set).mockImplementationOnce(() => new Promise<void>((resolve) => { finish = resolve }))
  const login = hybridAuthStorage.setItem("auth", "login")
  const logout = hybridAuthStorage.setItem("auth", "logout")
  await vi.waitFor(() => expect(SecureStorage.set).toHaveBeenCalledTimes(1))
  finish()
  await Promise.all([login, logout])
  expect(vi.mocked(SecureStorage.set).mock.calls.map((call) => call[1])).toEqual(["login", "logout"])
})

it("clears encrypted and legacy native copies on removal", async () => {
  await hybridAuthStorage.removeItem("auth")
  expect(SecureStorage.remove).toHaveBeenCalledWith("auth", false)
  expect(Preferences.remove).toHaveBeenCalledWith({ key: "auth" })
})

it("retains the existing web localStorage behavior", async () => {
  vi.mocked(Capacitor.isNativePlatform).mockReturnValue(false)
  await hybridAuthStorage.setItem("auth", "web-session")
  expect(await hybridAuthStorage.getItem("auth")).toBe("web-session")
  await hybridAuthStorage.removeItem("auth")
  expect(await hybridAuthStorage.getItem("auth")).toBeNull()
  expect(SecureStorage.set).not.toHaveBeenCalled()
  expect(Preferences.set).not.toHaveBeenCalled()
})

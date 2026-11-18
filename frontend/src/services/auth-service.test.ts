import { beforeEach, expect, it, vi } from "vitest"
import { apiClient } from "@/services/api-client"
import { useAuthStore, type UserProfile } from "@/stores/auth-store"
import { getMe, loginWithGoogle, logoutSession, refreshSession } from "./auth-service"

vi.mock("@/services/api-client", () => ({ apiClient: { post: vi.fn(), get: vi.fn() } }))
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
const profile = (id: string): UserProfile => ({ id, email: `${id}@example.com`, fullName: id, role: "MEMBER", skillPointsBalance: 0, reputationScore: 0, trustLevel: 0, isVerified: false })
beforeEach(() => { vi.clearAllMocks(); useAuthStore.getState().logout() })

it("uses the persisted wallet balance at login and identity synchronization", async () => {
  const user = { id: "member", email: "member@example.com", full_name: "Member", role: "MEMBER", skill_points_balance: 0 }
  vi.mocked(apiClient.post).mockResolvedValue({ statuscode: 200, message: "Autenticado", data: { user, access_token: "access", refresh_token: "refresh" } })
  await loginWithGoogle("google-credential")
  expect(useAuthStore.getState().user?.skillPointsBalance).toBe(0)
  vi.mocked(apiClient.get).mockResolvedValue({ statuscode: 200, message: "Identidad", data: { ...user, skill_points_balance: 42 } })
  await getMe()
  expect(useAuthStore.getState().user?.skillPointsBalance).toBe(42)
})

it("a delayed logout cannot clear a later account's session", async () => {
  useAuthStore.getState().login(profile("old"), "old-access", "old-refresh")
  let finish!: (value: { statuscode: number; message: string; data: null }) => void
  vi.mocked(apiClient.post).mockReturnValueOnce(new Promise((resolve) => { finish = resolve }))
  const loggingOut = logoutSession()
  useAuthStore.getState().login(profile("new"), "new-access", "new-refresh")
  finish({ statuscode: 200, message: "Sesión cerrada", data: null })
  await loggingOut
  expect(useAuthStore.getState().user?.id).toBe("new")
  expect(useAuthStore.getState().token).toBe("new-access")
})

it("a delayed manual refresh cannot replace a later account's credentials", async () => {
  useAuthStore.getState().login(profile("old"), "old-access", "old-refresh")
  let finish!: (value: { statuscode: number; message: string; data: { access_token: string; refresh_token: string; token_type: string; expires_in: number } }) => void
  vi.mocked(apiClient.post).mockReturnValueOnce(new Promise((resolve) => { finish = resolve }))
  const refreshing = refreshSession()
  useAuthStore.getState().login(profile("new"), "new-access", "new-refresh")
  finish({ statuscode: 200, message: "Renovada", data: { access_token: "rotated-old", refresh_token: "rotated-old-refresh", token_type: "bearer", expires_in: 3600 } })
  await expect(refreshing).rejects.toThrow("Solicitud de una sesión anterior descartada.")
  expect(useAuthStore.getState().token).toBe("new-access")
  expect(useAuthStore.getState().refreshToken).toBe("new-refresh")
})

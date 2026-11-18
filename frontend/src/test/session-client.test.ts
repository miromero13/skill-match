import { beforeEach, expect, it, vi } from "vitest"
import { apiClient } from "@/services/api-client"
import { useAuthStore } from "@/stores/auth-store"

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
beforeEach(() => {
  vi.unstubAllGlobals()
  useAuthStore.getState().login({ id: "member", email: "member@example.com", fullName: "Member", role: "MEMBER", skillPointsBalance: 0, reputationScore: 0, trustLevel: 0, isVerified: false }, "expired-access", "old-refresh")
})

it("logout after automatic refresh revokes the newly rotated refresh, not the consumed one", async () => {
  const reply = (status: number, data: unknown) => new Response(JSON.stringify({ statuscode: status, message: "Session response", data }), { status, headers: { "Content-Type": "application/json" } })
  const fetcher = vi.fn()
    .mockResolvedValueOnce(reply(401, null))
    .mockResolvedValueOnce(reply(200, { access_token: "new-access", refresh_token: "new-refresh" }))
    .mockResolvedValueOnce(reply(200, null))
  vi.stubGlobal("fetch", fetcher)
  await apiClient.post("/auth/logout", { refresh_token: "old-refresh" }, { showToastOnError: false })
  expect(fetcher).toHaveBeenCalledTimes(3)
  expect(JSON.parse(fetcher.mock.calls[2][1].body)).toEqual({ refresh_token: "new-refresh" })
  expect(new Headers(fetcher.mock.calls[2][1].headers).get("Authorization")).toBe("Bearer new-access")
})

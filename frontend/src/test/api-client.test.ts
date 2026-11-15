import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { apiClient } from "@/services/api-client"
import { useAuthStore, type UserProfile } from "@/stores/auth-store"
import { toast } from "sonner"

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }))
const user: UserProfile = {
  id: "A",
  fullName: "Member A",
  email: "a@example.invalid",
  role: "MEMBER",
  skillPointsBalance: 0,
  reputationScore: 0,
  trustLevel: 0,
  isVerified: false,
}
const response = (status: number, message: string, data: unknown = null) =>
  new Response(JSON.stringify({ statuscode: status, message, data }), {
    status,
    headers: { "Content-Type": "application/json" },
  })
beforeEach(() => {
  vi.clearAllMocks()
  useAuthStore.getState().login(user, "access-A", "refresh-A")
})
afterEach(() => vi.unstubAllGlobals())

it("preserves the backend 401 message and honors disabled toasts", async () => {
  useAuthStore.setState({ refreshToken: null })
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(response(401, "Token expirado del backend"))
  )
  await expect(
    apiClient.get("/private", { showToastOnError: false })
  ).rejects.toMatchObject({
    message: "Token expirado del backend",
    statuscode: 401,
  })
  expect(toast.error).not.toHaveBeenCalled()
  expect(useAuthStore.getState().isAuthenticated).toBe(false)
})
it("emits the backend error once", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(response(409, "Ya registraste esta evidencia."))
  )
  await expect(apiClient.post("/evidences", {})).rejects.toMatchObject({
    statuscode: 409,
  })
  expect(toast.error).toHaveBeenCalledExactlyOnceWith(
    "Ya registraste esta evidencia."
  )
})
it("keeps the session when the retried request has a validation error", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(response(401, "Token vencido"))
    .mockResolvedValueOnce(
      response(200, "Refrescado", {
        access_token: "new",
        refresh_token: "new-refresh",
      })
    )
    .mockResolvedValueOnce(response(422, "Error de validación del servidor"))
  vi.stubGlobal("fetch", fetchMock)
  await expect(apiClient.post("/evidences", {})).rejects.toMatchObject({
    statuscode: 422,
    message: "Error de validación del servidor",
  })
  expect(useAuthStore.getState()).toMatchObject({
    isAuthenticated: true,
    token: "new",
  })
  expect(toast.error).toHaveBeenCalledExactlyOnceWith(
    "Error de validación del servidor"
  )
})
it("does not show stale success or overwrite a new account", async () => {
  let resolve!: (value: Response) => void
  vi.stubGlobal(
    "fetch",
    vi.fn().mockReturnValue(
      new Promise<Response>((done) => {
        resolve = done
      })
    )
  )
  const request = apiClient.post("/evidences", {}, { showToastOnSuccess: true })
  useAuthStore.getState().login({ ...user, id: "B" }, "access-B", "refresh-B")
  resolve(response(201, "Creada", {}))
  await expect(request).rejects.toMatchObject({ statuscode: 0 })
  expect(toast.success).not.toHaveBeenCalled()
  expect(useAuthStore.getState().user?.id).toBe("B")
})
it("uses one refresh for concurrent requests", async () => {
  let resolveRefresh!: (value: Response) => void
  const pending = new Promise<Response>((done) => {
    resolveRefresh = done
  })
  const fetchMock = vi.fn((url: string, options: RequestInit) => {
    if (url.endsWith("/auth/refresh")) return pending
    const token = new Headers(options.headers).get("Authorization")
    return Promise.resolve(
      token === "Bearer new"
        ? response(200, "Listo", [])
        : response(401, "Vencido")
    )
  })
  vi.stubGlobal("fetch", fetchMock)
  const first = apiClient.get("/one")
  const second = apiClient.get("/two")
  await vi.waitFor(() =>
    expect(
      fetchMock.mock.calls.filter(([url]) => url.endsWith("/auth/refresh"))
    ).toHaveLength(1)
  )
  resolveRefresh(
    response(200, "Listo", {
      access_token: "new",
      refresh_token: "new-refresh",
    })
  )
  expect(
    (await Promise.all([first, second])).map((item) => item.statuscode)
  ).toEqual([200, 200])
})

it("discards a response from before logout even when the same user logs in again", async () => {
  let resolve!: (value: Response) => void
  vi.stubGlobal(
    "fetch",
    vi.fn().mockReturnValue(
      new Promise<Response>((done) => {
        resolve = done
      })
    )
  )
  const pending = apiClient.post("/evidences", {}, { showToastOnSuccess: true })
  useAuthStore.getState().logout()
  useAuthStore.getState().login(user, "second-session", "second-refresh")
  resolve(response(201, "Creada", {}))
  await expect(pending).rejects.toMatchObject({ statuscode: 0 })
  expect(toast.success).not.toHaveBeenCalled()
})

it("isolates an older pending refresh from the next account", async () => {
  let resolveOld!: (value: Response) => void
  const oldRefresh = new Promise<Response>((done) => {
    resolveOld = done
  })
  const fetchMock = vi.fn((url: string, options: RequestInit) => {
    if (url.endsWith("/auth/refresh")) {
      const body = JSON.parse(String(options.body)) as { refresh_token: string }
      return body.refresh_token === "refresh-A"
        ? oldRefresh
        : Promise.resolve(
            response(200, "Refrescado", {
              access_token: "B-new",
              refresh_token: "B-refresh-new",
            })
          )
    }
    return Promise.resolve(
      new Headers(options.headers).get("Authorization") === "Bearer B-new"
        ? response(200, "Listo", [])
        : response(401, "Vencido")
    )
  })
  vi.stubGlobal("fetch", fetchMock)
  const old = apiClient.get("/old")
  await vi.waitFor(() =>
    expect(
      fetchMock.mock.calls.some(([url]) => url.endsWith("/auth/refresh"))
    ).toBe(true)
  )
  useAuthStore.getState().login({ ...user, id: "B" }, "B-access", "B-refresh")
  expect((await apiClient.get("/new")).statuscode).toBe(200)
  resolveOld(
    response(200, "Old", {
      access_token: "A-new",
      refresh_token: "A-refresh-new",
    })
  )
  await expect(old).rejects.toMatchObject({ statuscode: 0 })
  expect(useAuthStore.getState()).toMatchObject({
    token: "B-new",
    user: { id: "B" },
    isAuthenticated: true,
  })
  expect(toast.error).not.toHaveBeenCalled()
})

import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { toast } from "sonner"
import { useAuthStore, type UserProfile } from "@/stores/auth-store"
import { useNotificationStore as store } from "@/stores/notification-store"

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }))
const user: UserProfile = {
  id: "A",
  email: "a@example.invalid",
  fullName: "A",
  role: "MEMBER",
  skillPointsBalance: 0,
  reputationScore: 0,
  trustLevel: 0,
  isVerified: false,
}
const preferences = {
  revision: 0,
  channels: { in_app: true, push: false, email: false },
  categories: { INTERCHANGES: true, POINTS: true, GENERAL: true },
}
const reply = (
  status: number,
  message: string,
  data: unknown = null,
  count?: number
) =>
  new Response(
    JSON.stringify({
      statuscode: status,
      message,
      data,
      ...(count === undefined ? {} : { count }),
    }),
    { status, headers: { "Content-Type": "application/json" } }
  )
beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal("fetch", vi.fn())
  useAuthStore.getState().login(user, "access-A")
  store.getState().reset()
})
afterEach(() => vi.unstubAllGlobals())

it("shows the server's 401 message once even when the shared client logs out", async () => {
  vi.mocked(fetch).mockResolvedValue(
    reply(401, "Sesión expirada indicada por el servidor.")
  )
  expect(await store.getState().markAllRead()).toBe(false)
  expect(useAuthStore.getState().isAuthenticated).toBe(false)
  expect(toast.error).toHaveBeenCalledExactlyOnceWith(
    "Sesión expirada indicada por el servidor."
  )
})

it("preserves a revision conflict and shows exactly one backend message", async () => {
  store.setState({ draft: preferences, dirty: true })
  vi.mocked(fetch).mockResolvedValue(
    reply(
      409,
      "Las preferencias cambiaron. Recarga la configuración antes de guardar."
    )
  )
  expect(await store.getState().savePreferences()).toBe(false)
  expect(store.getState()).toMatchObject({
    draft: preferences,
    dirty: true,
    preferencesConflict: true,
  })
  expect(toast.error).toHaveBeenCalledTimes(1)
  expect(toast.error).toHaveBeenCalledWith(
    "Las preferencias cambiaron. Recarga la configuración antes de guardar."
  )
})

it("uses real client serialization and a separate global unread query with Bearer headers", async () => {
  vi.mocked(fetch)
    .mockResolvedValueOnce(
      reply(200, "Notificaciones recuperadas exitosamente.", [], 12)
    )
    .mockResolvedValueOnce(
      reply(200, "Notificaciones recuperadas exitosamente.", [], 41)
    )
  store.getState().setFilters({ category: "POINTS", unread: false })
  await store.getState().loadList()
  await store.getState().loadUnread()
  const list = new URL(
    String(vi.mocked(fetch).mock.calls[0][0]),
    "http://testserver"
  )
  const unread = new URL(
    String(vi.mocked(fetch).mock.calls[1][0]),
    "http://testserver"
  )
  expect(list.searchParams.get("unread")).toBe("false")
  expect(list.searchParams.get("category")).toBe("POINTS")
  expect(unread.searchParams.has("category")).toBe(false)
  expect(unread.searchParams.get("unread")).toBe("true")
  expect(
    new Headers(vi.mocked(fetch).mock.calls[0][1]?.headers).get("Authorization")
  ).toBe("Bearer access-A")
  expect(store.getState()).toMatchObject({ total: 12, unreadTotal: 41 })
})

it("discards another account's late error without showing its message", async () => {
  let resolve!: (response: Response) => void
  vi.mocked(fetch).mockReturnValue(
    new Promise<Response>((done) => {
      resolve = done
    })
  )
  const pending = store.getState().markAllRead()
  useAuthStore.getState().login({ ...user, id: "B" }, "access-B")
  resolve(reply(409, "Mensaje privado de la cuenta anterior"))
  expect(await pending).toBe(false)
  expect(toast.error).not.toHaveBeenCalled()
  expect(toast.success).not.toHaveBeenCalled()
})

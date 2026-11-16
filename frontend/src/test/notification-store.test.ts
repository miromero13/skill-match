import { beforeEach, expect, it, vi } from "vitest"
import { toast } from "sonner"
import { useAuthStore, type UserProfile } from "@/stores/auth-store"
import { useNotificationStore as store } from "@/stores/notification-store"
import * as service from "@/services/notification-service"
import { ApiError, type APIResponse } from "@/types/api"
import type {
  NotificationItem,
  NotificationPreferences,
} from "@/types/notification"

vi.mock("@/services/notification-service")
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
const item: NotificationItem = {
  id: "n1",
  type: "POINTS_RECEIVED",
  category: "POINTS",
  title: "Title",
  message: "Message",
  created_at: "2026-11-16T00:00:00Z",
  read_at: null,
}
const preferences = (): NotificationPreferences => ({
  revision: 0,
  channels: { in_app: true, push: false, email: false },
  categories: { INTERCHANGES: true, POINTS: true, GENERAL: true },
})
const response = <T>(data: T, message = "Servidor"): APIResponse<T> => ({
  statuscode: 200,
  message,
  data,
})
const list = (items: NotificationItem[] = [], count = items.length) => ({
  ...response(items),
  count,
})
function deferred<T>() {
  let resolve!: (result: T) => void
  const promise = new Promise<T>((done) => {
    resolve = done
  })
  return { promise, resolve }
}
beforeEach(() => {
  vi.resetAllMocks()
  useAuthStore.getState().login(user, "access", "refresh")
  store.getState().reset()
  vi.mocked(service.getNotifications).mockResolvedValue(list())
  vi.mocked(service.getUnreadCount).mockResolvedValue(0)
})

it("uses a global server count independently from visible filters and rows", async () => {
  store.getState().setFilters({ category: "POINTS" })
  vi.mocked(service.getNotifications).mockResolvedValue(list([item], 12))
  vi.mocked(service.getUnreadCount).mockResolvedValue(41)
  await Promise.all([
    store.getState().loadList(),
    store.getState().loadUnread(),
  ])
  expect(store.getState()).toMatchObject({
    items: [item],
    total: 12,
    unreadTotal: 41,
  })
})

it("resets pagination and discards a slow result after changing filters", async () => {
  const old = deferred<ReturnType<typeof list>>()
  vi.mocked(service.getNotifications)
    .mockReturnValueOnce(old.promise)
    .mockResolvedValueOnce(list([], 3))
  const request = store.getState().loadList(2)
  store.getState().setFilters({ unread: true })
  await store.getState().loadList()
  old.resolve(list([item], 99))
  await request
  expect(store.getState()).toMatchObject({
    page: 1,
    filters: { unread: true },
    items: [],
    total: 3,
    loading: false,
  })
})

it("clears private state and discards pending results after logout or switching account", async () => {
  const pending = deferred<ReturnType<typeof list>>()
  vi.mocked(service.getNotifications).mockReturnValueOnce(pending.promise)
  const request = store.getState().loadList()
  useAuthStore.getState().logout()
  useAuthStore.getState().login({ ...user, id: "B", role: "ADMIN" }, "access-B")
  pending.resolve(list([item], 9))
  await request
  expect(store.getState()).toMatchObject({
    items: [],
    total: 0,
    unreadTotal: 0,
    preferences: null,
    draft: null,
  })
})

it("resets on same-account relogin but preserves state when rotating tokens", () => {
  store.setState({ unreadTotal: 5 })
  useAuthStore.getState().setTokens("new-access", "new-refresh")
  expect(store.getState().unreadTotal).toBe(5)
  useAuthStore.getState().login(user, "new-login")
  expect(store.getState().unreadTotal).toBe(0)
})

it("does not issue requests without an authenticated session", async () => {
  useAuthStore.getState().logout()
  expect(await store.getState().loadList()).toBe(false)
  expect(await store.getState().loadUnread()).toBe(false)
  expect(await store.getState().loadPreferences()).toBe(false)
  expect(service.getNotifications).not.toHaveBeenCalled()
})

it("preserves a confirmed mutation when refresh fails and prevents double submission", async () => {
  const pending = deferred<APIResponse<NotificationItem>>()
  vi.mocked(service.markNotificationRead).mockReturnValueOnce(pending.promise)
  vi.mocked(service.getNotifications).mockRejectedValueOnce(
    new Error("Recarga fallida")
  )
  const first = store.getState().markRead("n1")
  expect(await store.getState().markRead("n1")).toBe(false)
  pending.resolve(
    response(
      { ...item, read_at: item.created_at },
      "Notificación marcada como leída."
    )
  )
  expect(await first).toBe(true)
  expect(service.markNotificationRead).toHaveBeenCalledTimes(1)
  expect(store.getState().listError).toBe("Recarga fallida")
  expect(toast.success).toHaveBeenCalledWith("Notificación marcada como leída.")
})

it("returns to the previous page after deleting its last visible item", async () => {
  store.setState({ items: [item], page: 2, total: 21 })
  vi.mocked(service.deleteNotification).mockResolvedValue(response(null))
  await store.getState().remove("n1")
  expect(service.getNotifications).toHaveBeenLastCalledWith({}, 1, 20)
})

it("never blindly decrements the badge after repeated read-all", async () => {
  vi.mocked(service.markAllNotificationsRead).mockResolvedValue(response(null))
  vi.mocked(service.getUnreadCount)
    .mockResolvedValueOnce(1)
    .mockResolvedValueOnce(2)
  await store.getState().markAllRead()
  expect(store.getState().unreadTotal).toBe(1)
  await store.getState().markAllRead()
  expect(store.getState().unreadTotal).toBe(2)
})

it("loads server preferences, preserves edits on 409 and explicitly reloads to reconcile", async () => {
  vi.mocked(service.getNotificationPreferences).mockResolvedValue(
    response(preferences())
  )
  await store.getState().loadPreferences()
  const draft = preferences()
  draft.channels.push = true
  store.getState().editPreferences(draft)
  vi.mocked(service.updateNotificationPreferences).mockRejectedValue(
    new ApiError("Las preferencias cambiaron.", 409)
  )
  expect(await store.getState().savePreferences()).toBe(false)
  expect(store.getState()).toMatchObject({
    draft,
    dirty: true,
    preferencesConflict: true,
    preferencesError: "Las preferencias cambiaron.",
  })
  vi.mocked(service.getNotificationPreferences).mockResolvedValue(
    response({ ...preferences(), revision: 2 })
  )
  await store.getState().loadPreferences(true)
  expect(store.getState()).toMatchObject({
    draft: { ...preferences(), revision: 2 },
    dirty: false,
    preferencesConflict: false,
  })
})

it("does not overwrite a dirty draft during background preference loading", async () => {
  vi.mocked(service.getNotificationPreferences).mockResolvedValue(
    response(preferences())
  )
  await store.getState().loadPreferences()
  const pending = deferred<APIResponse<NotificationPreferences>>()
  vi.mocked(service.getNotificationPreferences).mockReturnValueOnce(
    pending.promise
  )
  const loading = store.getState().loadPreferences()
  const draft = preferences()
  draft.channels.email = true
  store.getState().editPreferences(draft)
  pending.resolve(response({ ...preferences(), revision: 3 }))
  await loading
  expect(store.getState().draft).toEqual(draft)
})

it("saves complete preferences with the server revision and independent nested values", async () => {
  vi.mocked(service.getNotificationPreferences).mockResolvedValue(
    response(preferences())
  )
  await store.getState().loadPreferences()
  const draft = preferences()
  draft.channels.push = true
  store.getState().editPreferences(draft)
  draft.channels.email = true
  vi.mocked(service.updateNotificationPreferences).mockResolvedValue(
    response({
      ...preferences(),
      revision: 1,
      channels: { in_app: true, push: true, email: false },
    })
  )
  expect(await store.getState().savePreferences()).toBe(true)
  expect(service.updateNotificationPreferences).toHaveBeenCalledWith({
    ...preferences(),
    channels: { in_app: true, push: true, email: false },
  })
  expect(store.getState()).toMatchObject({
    dirty: false,
    preferences: { revision: 1 },
  })
})

it("does not show a mutation result or toast from a previous session", async () => {
  const pending = deferred<APIResponse<null>>()
  vi.mocked(service.markAllNotificationsRead).mockReturnValueOnce(
    pending.promise
  )
  const request = store.getState().markAllRead()
  useAuthStore.getState().logout()
  pending.resolve(response(null))
  expect(await request).toBe(false)
  expect(toast.success).not.toHaveBeenCalled()
})

it("discards an older unread count after a newer request", async () => {
  const old = deferred<number>()
  vi.mocked(service.getUnreadCount)
    .mockReturnValueOnce(old.promise)
    .mockResolvedValueOnce(2)
  const first = store.getState().loadUnread()
  await store.getState().loadUnread()
  old.resolve(99)
  await first
  expect(store.getState()).toMatchObject({
    unreadTotal: 2,
    unreadLoading: false,
  })
})

it("invalidates pre-mutation list and counter responses", async () => {
  const oldList = deferred<ReturnType<typeof list>>()
  const oldCount = deferred<number>()
  vi.mocked(service.getNotifications)
    .mockReturnValueOnce(oldList.promise)
    .mockResolvedValueOnce(list([], 3))
  vi.mocked(service.getUnreadCount)
    .mockReturnValueOnce(oldCount.promise)
    .mockResolvedValueOnce(1)
  const loading = store.getState().loadList()
  const counting = store.getState().loadUnread()
  vi.mocked(service.markAllNotificationsRead).mockResolvedValue(response(null))
  await store.getState().markAllRead()
  oldList.resolve(list([item], 99))
  oldCount.resolve(99)
  await Promise.all([loading, counting])
  expect(store.getState()).toMatchObject({
    total: 3,
    unreadTotal: 1,
    items: [],
  })
})

it("preserves the last known count with an explicit refresh error", async () => {
  store.setState({ unreadTotal: 12 })
  vi.mocked(service.getUnreadCount).mockRejectedValue(
    new Error("No se pudo consultar el total")
  )
  expect(await store.getState().loadUnread()).toBe(false)
  expect(store.getState()).toMatchObject({
    unreadTotal: 12,
    unreadError: "No se pudo consultar el total",
  })
})

it("does not let the editor forge the server revision", async () => {
  vi.mocked(service.getNotificationPreferences).mockResolvedValue(
    response(preferences())
  )
  await store.getState().loadPreferences()
  store.getState().editPreferences({ ...preferences(), revision: 999 })
  expect(store.getState().draft?.revision).toBe(0)
})

it("prevents double save and discards a GET started before a confirmed save", async () => {
  vi.mocked(service.getNotificationPreferences).mockResolvedValue(
    response(preferences())
  )
  await store.getState().loadPreferences()
  const oldGet = deferred<APIResponse<NotificationPreferences>>()
  vi.mocked(service.getNotificationPreferences).mockReturnValueOnce(
    oldGet.promise
  )
  const loading = store.getState().loadPreferences()
  store.getState().editPreferences(preferences())
  const pending = deferred<APIResponse<NotificationPreferences>>()
  vi.mocked(service.updateNotificationPreferences).mockReturnValueOnce(
    pending.promise
  )
  const saving = store.getState().savePreferences()
  expect(await store.getState().savePreferences()).toBe(false)
  pending.resolve(response({ ...preferences(), revision: 1 }))
  expect(await saving).toBe(true)
  oldGet.resolve(response(preferences()))
  await loading
  expect(store.getState()).toMatchObject({
    preferences: { revision: 1 },
    draft: { revision: 1 },
    preferencesLoading: false,
    preferencesSaving: false,
  })
})

it("does not restore old preferences or counters after switching sessions", async () => {
  const pendingPrefs = deferred<APIResponse<NotificationPreferences>>()
  const pendingCount = deferred<number>()
  vi.mocked(service.getNotificationPreferences).mockReturnValueOnce(
    pendingPrefs.promise
  )
  vi.mocked(service.getUnreadCount).mockReturnValueOnce(pendingCount.promise)
  const loading = store.getState().loadPreferences()
  const counting = store.getState().loadUnread()
  useAuthStore.getState().login({ ...user, id: "B" }, "access-B")
  pendingPrefs.resolve(response(preferences()))
  pendingCount.resolve(99)
  await Promise.all([loading, counting])
  expect(store.getState()).toMatchObject({
    preferences: null,
    draft: null,
    unreadTotal: 0,
    preferencesLoading: false,
    unreadLoading: false,
  })
})

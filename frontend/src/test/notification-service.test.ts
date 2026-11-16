import { beforeEach, expect, it, vi } from "vitest"
import { apiClient } from "@/services/api-client"
import * as service from "@/services/notification-service"

vi.mock("@/services/api-client", () => ({
  apiClient: { get: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))
const requestOptions = { showToastOnError: true, showToastOnSuccess: false }
beforeEach(() => vi.clearAllMocks())

it("uses the agreed filters and pagination without inventing an unread endpoint", async () => {
  vi.mocked(apiClient.get).mockResolvedValue({
    statuscode: 200,
    message: "Loaded",
    data: [],
    count: 7,
  })
  await service.getNotifications({ category: "POINTS", unread: false }, 2, 20)
  expect(apiClient.get).toHaveBeenCalledWith("/notifications", {
    ...requestOptions,
    params: { category: "POINTS", unread: false, page: 2, page_size: 20 },
  })
  expect(await service.getUnreadCount()).toBe(7)
  expect(apiClient.get).toHaveBeenLastCalledWith("/notifications", {
    ...requestOptions,
    params: { unread: true, page: 1, page_size: 1 },
  })
})

it("uses the six existing operations and sends a complete revisioned preference body", async () => {
  const preferences = {
    revision: 1,
    channels: { in_app: true, push: false, email: false },
    categories: { INTERCHANGES: true, POINTS: true, GENERAL: true },
  }
  await service.markNotificationRead("a/b")
  await service.markAllNotificationsRead()
  await service.deleteNotification("a/b")
  await service.getNotificationPreferences()
  await service.updateNotificationPreferences(preferences)
  expect(apiClient.patch).toHaveBeenCalledWith(
    "/notifications/a%2Fb/read",
    undefined,
    requestOptions
  )
  expect(apiClient.patch).toHaveBeenCalledWith(
    "/notifications/read-all",
    undefined,
    requestOptions
  )
  expect(apiClient.delete).toHaveBeenCalledWith(
    "/notifications/a%2Fb",
    requestOptions
  )
  expect(apiClient.get).toHaveBeenCalledWith(
    "/users/me/notification-preferences",
    requestOptions
  )
  expect(apiClient.put).toHaveBeenCalledWith(
    "/users/me/notification-preferences",
    preferences,
    requestOptions
  )
})

it("does not silently substitute zero for a missing or invalid total", async () => {
  vi.mocked(apiClient.get).mockResolvedValue({
    statuscode: 200,
    message: "Loaded",
    data: [],
  })
  await expect(service.getUnreadCount()).rejects.toThrow()
})

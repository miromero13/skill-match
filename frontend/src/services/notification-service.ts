import { apiClient } from "@/services/api-client"
import type {
  NotificationFilters,
  NotificationItem,
  NotificationPreferences,
} from "@/types/notification"

// The shared client owns backend error messages, including a 401 that logs out
// and resets the store. The store owns success toasts after its session guard.
const requestOptions = { showToastOnError: true, showToastOnSuccess: false }
const base = "/notifications"
const preferences = "/users/me/notification-preferences"

export async function getNotifications(
  filters: NotificationFilters = {},
  page = 1,
  pageSize = 20
) {
  const response = await apiClient.get<NotificationItem[]>(base, {
    ...requestOptions,
    params: { ...filters, page, page_size: pageSize },
  })
  if (
    response.count == null ||
    !Number.isSafeInteger(response.count) ||
    response.count < 0
  )
    throw new Error(
      "La respuesta no contiene un total de notificaciones válido."
    )
  return { ...response, count: response.count }
}
export async function getUnreadCount() {
  return (await getNotifications({ unread: true }, 1, 1)).count
}
export function markNotificationRead(id: string) {
  return apiClient.patch<NotificationItem>(
    `${base}/${encodeURIComponent(id)}/read`,
    undefined,
    requestOptions
  )
}
export function markAllNotificationsRead() {
  return apiClient.patch<null>(`${base}/read-all`, undefined, requestOptions)
}
export function deleteNotification(id: string) {
  return apiClient.delete<null>(
    `${base}/${encodeURIComponent(id)}`,
    requestOptions
  )
}
export function getNotificationPreferences() {
  return apiClient.get<NotificationPreferences>(preferences, requestOptions)
}
export function updateNotificationPreferences(
  payload: NotificationPreferences
) {
  return apiClient.put<NotificationPreferences>(
    preferences,
    payload,
    requestOptions
  )
}

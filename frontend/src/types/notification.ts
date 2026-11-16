export const notificationTypes = [
  "MATCH_RECEIVED",
  "MATCH_CONFIRMED",
  "SESSION_PROPOSED",
  "POINTS_RECEIVED",
  "OTHER",
] as const
export const notificationCategories = [
  "INTERCHANGES",
  "POINTS",
  "GENERAL",
] as const
export type NotificationType = (typeof notificationTypes)[number]
export type NotificationCategory = (typeof notificationCategories)[number]

export interface NotificationItem {
  id: string
  type: NotificationType
  category: NotificationCategory
  title: string
  message: string
  created_at: string
  read_at: string | null
}
export interface NotificationFilters {
  unread?: boolean
  category?: NotificationCategory
}
export interface NotificationPreferences {
  revision: number
  channels: { in_app: boolean; push: boolean; email: boolean }
  categories: Record<NotificationCategory, boolean>
}

export function cloneNotificationPreferences(
  value: NotificationPreferences
): NotificationPreferences {
  return {
    revision: value.revision,
    channels: { ...value.channels },
    categories: { ...value.categories },
  }
}

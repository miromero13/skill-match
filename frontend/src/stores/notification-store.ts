import { create } from "zustand"
import { toast } from "sonner"
import { ApiError, type APIResponse } from "@/types/api"
import {
  cloneNotificationPreferences,
  type NotificationFilters,
  type NotificationItem,
  type NotificationPreferences,
} from "@/types/notification"
import * as service from "@/services/notification-service"
import { getAuthSessionVersion, useAuthStore } from "@/stores/auth-store"

interface NotificationState {
  items: NotificationItem[]
  filters: NotificationFilters
  page: number
  total: number
  unreadTotal: number
  realtimeRevision: number
  loading: boolean
  unreadLoading: boolean
  mutating: boolean
  listError: string | null
  unreadError: string | null
  mutationError: string | null
  preferences: NotificationPreferences | null
  draft: NotificationPreferences | null
  dirty: boolean
  preferencesLoading: boolean
  preferencesSaving: boolean
  preferencesError: string | null
  preferencesConflict: boolean
  reset: () => void
  setFilters: (filters: NotificationFilters) => void
  loadList: (page?: number) => Promise<boolean>
  loadUnread: () => Promise<boolean>
  markRead: (id: string) => Promise<boolean>
  markAllRead: () => Promise<boolean>
  remove: (id: string) => Promise<boolean>
  loadPreferences: (replaceDraft?: boolean) => Promise<boolean>
  discardPreferences: () => void
  editPreferences: (draft: NotificationPreferences) => void
  savePreferences: () => Promise<boolean>
}

const initial = () => ({
  items: [] as NotificationItem[],
  filters: {} as NotificationFilters,
  page: 1,
  total: 0,
  unreadTotal: 0,
  realtimeRevision: 0,
  loading: false,
  unreadLoading: false,
  mutating: false,
  listError: null,
  unreadError: null,
  mutationError: null,
  preferences: null,
  draft: null,
  dirty: false,
  preferencesLoading: false,
  preferencesSaving: false,
  preferencesError: null,
  preferencesConflict: false,
})
let generation = 0
let listRequest = 0
let unreadRequest = 0
let preferenceRequest = 0
let editVersion = 0
const authenticated = () => {
  const auth = useAuthStore.getState()
  return Boolean(auth.isAuthenticated && auth.token && auth.user?.id)
}
const message = (error: unknown) =>
  error instanceof Error ? error.message : "No se pudo completar la solicitud."

async function mutate(
  operation: () => Promise<APIResponse<NotificationItem | null>>,
  removedId?: string
) {
  const state = useNotificationStore.getState()
  if (!authenticated() || state.mutating) return false
  const epoch = generation
  listRequest++
  unreadRequest++
  useNotificationStore.setState({
    mutating: true,
    mutationError: null,
    loading: false,
    unreadLoading: false,
  })
  try {
    const response = await operation()
    if (epoch !== generation) return false
    listRequest++
    unreadRequest++
    const current = useNotificationStore.getState()
    if (removedId && current.items.some((item) => item.id === removedId)) {
      useNotificationStore.setState({
        items: current.items.filter((item) => item.id !== removedId),
        total: Math.max(0, current.total - 1),
        page:
          current.items.length === 1
            ? Math.max(1, current.page - 1)
            : current.page,
      })
    }
    toast.success(response.message)
    // Read the authoritative total: read-all may race with a newly created notice.
    // A confirmed write remains successful if either refresh fails.
    await Promise.all([
      useNotificationStore.getState().loadList(),
      useNotificationStore.getState().loadUnread(),
    ])
    return epoch === generation
  } catch (error) {
    if (epoch === generation) {
      useNotificationStore.setState({ mutationError: message(error) })
      if (!(error instanceof ApiError)) toast.error(message(error))
    }
    return false
  } finally {
    if (epoch === generation) useNotificationStore.setState({ mutating: false })
  }
}

export const useNotificationStore = create<NotificationState>((set, get) => ({
  ...initial(),
  reset: () => {
    generation++
    listRequest++
    unreadRequest++
    preferenceRequest++
    editVersion++
    set(initial())
  },
  setFilters: (filters) => {
    listRequest++
    set({
      filters: { ...filters },
      page: 1,
      items: [],
      total: 0,
      loading: false,
      listError: null,
    })
  },
  loadList: async (page = get().page) => {
    if (!authenticated()) return false
    const epoch = generation
    const request = ++listRequest
    const filters = { ...get().filters }
    set({ page, loading: true, listError: null })
    try {
      const response = await service.getNotifications(filters, page, 20)
      if (epoch !== generation || request !== listRequest) return false
      set({ items: response.data, total: response.count })
      return true
    } catch (error) {
      if (epoch === generation && request === listRequest)
        set({ listError: message(error) })
      return false
    } finally {
      if (epoch === generation && request === listRequest)
        set({ loading: false })
    }
  },
  loadUnread: async () => {
    if (!authenticated()) return false
    const epoch = generation
    const request = ++unreadRequest
    set({ unreadLoading: true, unreadError: null })
    try {
      const count = await service.getUnreadCount()
      if (epoch !== generation || request !== unreadRequest) return false
      set({ unreadTotal: count })
      return true
    } catch (error) {
      if (epoch === generation && request === unreadRequest)
        set({ unreadError: message(error) })
      return false
    } finally {
      if (epoch === generation && request === unreadRequest)
        set({ unreadLoading: false })
    }
  },
  markRead: (id) => mutate(() => service.markNotificationRead(id)),
  markAllRead: () => mutate(service.markAllNotificationsRead),
  remove: (id) => mutate(() => service.deleteNotification(id), id),
  loadPreferences: async (replaceDraft = false) => {
    if (!authenticated() || get().preferencesSaving) return false
    const epoch = generation
    const request = ++preferenceRequest
    const editing = editVersion
    set({ preferencesLoading: true, preferencesError: null })
    try {
      const response = await service.getNotificationPreferences()
      if (epoch !== generation || request !== preferenceRequest) return false
      const preferences = cloneNotificationPreferences(response.data)
      const replace = editing === editVersion && (replaceDraft || !get().dirty)
      set({
        preferences,
        ...(replace
          ? {
              draft: cloneNotificationPreferences(preferences),
              dirty: false,
              preferencesConflict: false,
            }
          : {
              preferencesConflict:
                get().preferencesConflict ||
                get().draft?.revision !== preferences.revision,
            }),
      })
      return true
    } catch (error) {
      if (epoch === generation && request === preferenceRequest)
        set({ preferencesError: message(error) })
      return false
    } finally {
      if (epoch === generation && request === preferenceRequest)
        set({ preferencesLoading: false })
    }
  },
  discardPreferences: () => {
    editVersion++
    const preferences = get().preferences
    set({
      draft: preferences ? cloneNotificationPreferences(preferences) : null,
      dirty: false,
      preferencesConflict: false,
      preferencesError: null,
    })
  },
  editPreferences: (value) => {
    const current = get().draft
    if (!authenticated() || !current || get().preferencesSaving) return
    editVersion++
    set({
      draft: cloneNotificationPreferences({
        ...value,
        revision: current.revision,
      }),
      dirty: true,
    })
  },
  savePreferences: async () => {
    const draft = get().draft
    if (!authenticated() || !draft || !get().dirty || get().preferencesSaving)
      return false
    const epoch = generation
    const payload = cloneNotificationPreferences(draft)
    preferenceRequest++
    set({
      preferencesSaving: true,
      preferencesLoading: false,
      preferencesError: null,
    })
    try {
      const response = await service.updateNotificationPreferences(payload)
      if (epoch !== generation) return false
      set({
        preferences: cloneNotificationPreferences(response.data),
        draft: cloneNotificationPreferences(response.data),
        dirty: false,
        preferencesConflict: false,
      })
      toast.success(response.message)
      return true
    } catch (error) {
      if (epoch === generation) {
        set({
          preferencesError: message(error),
          preferencesConflict:
            error instanceof ApiError && error.statuscode === 409,
        })
        if (!(error instanceof ApiError)) toast.error(message(error))
      }
      return false
    } finally {
      if (epoch === generation) set({ preferencesSaving: false })
    }
  },
}))

let authVersion = getAuthSessionVersion()
useAuthStore.subscribe((state, previous) => {
  if (
    authVersion !== getAuthSessionVersion() ||
    state.user?.id !== previous.user?.id ||
    state.user?.role !== previous.user?.role ||
    state.isAuthenticated !== previous.isAuthenticated
  ) {
    authVersion = getAuthSessionVersion()
    useNotificationStore.getState().reset()
  }
})

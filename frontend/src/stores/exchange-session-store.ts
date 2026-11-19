import { toast } from "sonner"
import { create } from "zustand"

import * as service from "@/services/exchange-session-service"
import { getAuthSessionVersion, useAuthStore } from "@/stores/auth-store"
import { ApiError, type APIResponse } from "@/types/api"
import type {
  ExchangeSession,
  ExchangeSessionCreate,
  ExchangeSessionReschedule,
} from "@/types/exchange-session"

interface ExchangeSessionState {
  items: ExchangeSession[]
  total: number
  page: number
  freeSessionsLeft: number
  freeSessionsLimit: number
  loading: boolean
  loaded: boolean
  error: string | null
  pending: Record<string, boolean>
  reset: () => void
  load: (page?: number) => Promise<boolean>
  create: (payload: ExchangeSessionCreate) => Promise<boolean>
  accept: (id: string) => Promise<boolean>
  reject: (id: string) => Promise<boolean>
  reschedule: (
    id: string,
    payload: ExchangeSessionReschedule
  ) => Promise<boolean>
  cancel: (id: string, cancellationReason: string) => Promise<boolean>
}

const initial = () => ({
  items: [] as ExchangeSession[],
  total: 0,
  page: 1,
  freeSessionsLeft: 0,
  freeSessionsLimit: 2,
  loading: false,
  loaded: false,
  error: null as string | null,
  pending: {} as Record<string, boolean>,
})

let generation = 0
let listRequest = 0

const authenticated = () => {
  const auth = useAuthStore.getState()
  return Boolean(auth.isAuthenticated && auth.token && auth.user?.id)
}
const errorMessage = (error: unknown) =>
  error instanceof Error ? error.message : "No se pudo completar la solicitud."
const replaceItem = (items: ExchangeSession[], item: ExchangeSession) =>
  items.some((current) => current.id === item.id)
    ? items.map((current) => (current.id === item.id ? item : current))
    : [item, ...items]

async function mutate(
  key: string,
  operation: () => Promise<APIResponse<ExchangeSession>>,
  apply: (
    state: ExchangeSessionState,
    item: ExchangeSession
  ) => Partial<ExchangeSessionState>
) {
  const state = useExchangeSessionStore.getState()
  if (!authenticated() || state.pending[key]) return false
  const epoch = generation
  listRequest++
  useExchangeSessionStore.setState((current) => ({
    pending: { ...current.pending, [key]: true },
    error: null,
    loading: false,
  }))
  try {
    const response = await operation()
    if (epoch !== generation) return false
    useExchangeSessionStore.setState((current) => apply(current, response.data))
    toast.success(response.message)
    return true
  } catch (error) {
    if (epoch === generation) {
      useExchangeSessionStore.setState({ error: errorMessage(error) })
      if (!(error instanceof ApiError)) toast.error(errorMessage(error))
    }
    return false
  } finally {
    if (epoch === generation)
      useExchangeSessionStore.setState((current) => {
        const pending = { ...current.pending }
        delete pending[key]
        return { pending }
      })
  }
}

export const useExchangeSessionStore = create<ExchangeSessionState>(
  (set, get) => ({
    ...initial(),
    reset: () => {
      generation++
      listRequest++
      set(initial())
    },
    load: async (page = get().page) => {
      if (!authenticated()) return false
      const epoch = generation
      const request = ++listRequest
      set({ page, loading: true, error: null })
      try {
        const response = await service.getExchangeSessions(page, 20)
        if (epoch !== generation || request !== listRequest) return false
        set({
          items: response.data.items,
          total: response.count,
          freeSessionsLeft: response.data.free_sessions_left,
          freeSessionsLimit: response.data.free_sessions_limit,
          loaded: true,
        })
        return true
      } catch (error) {
        if (epoch === generation && request === listRequest)
          set({ error: errorMessage(error), loaded: true })
        return false
      } finally {
        if (epoch === generation && request === listRequest)
          set({ loading: false })
      }
    },
    create: (payload) =>
      mutate(
        "create",
        () => service.createExchangeSession(payload),
        (state, item) => ({
          items: replaceItem(state.items, item),
          total: state.items.some((current) => current.id === item.id)
            ? state.total
            : state.total + 1,
          freeSessionsLeft: item.is_free
            ? Math.max(0, state.freeSessionsLeft - 1)
            : state.freeSessionsLeft,
          loaded: true,
        })
      ),
    accept: (id) =>
      mutate(
        `status:${id}`,
        () => service.acceptExchangeSession(id),
        (state, item) => ({
          items: replaceItem(state.items, item),
        })
      ),
    reject: (id) =>
      mutate(
        `status:${id}`,
        () => service.rejectExchangeSession(id),
        (state, item) => ({
          items: replaceItem(state.items, item),
          freeSessionsLeft:
            state.items.find((current) => current.id === item.id)?.status !==
              "REJECTED" && item.learner_id === useAuthStore.getState().user?.id
              ? Math.min(state.freeSessionsLimit, state.freeSessionsLeft + 1)
              : state.freeSessionsLeft,
        })
      ),
    reschedule: (id, payload) =>
      mutate(
        `reschedule:${id}`,
        () => service.rescheduleExchangeSession(id, payload),
        (state, item) => ({ items: replaceItem(state.items, item) })
      ),
    cancel: (id, cancellationReason) =>
      mutate(
        `cancel:${id}`,
        () => service.cancelExchangeSession(id, cancellationReason),
        (state, item) => ({
          items: replaceItem(state.items, item),
          freeSessionsLeft:
            state.items.find((current) => current.id === item.id)?.status !==
              "CANCELLED" &&
            item.quota_restored &&
            item.learner_id === useAuthStore.getState().user?.id
              ? Math.min(state.freeSessionsLimit, state.freeSessionsLeft + 1)
              : state.freeSessionsLeft,
        })
      ),
  })
)

let authVersion = getAuthSessionVersion()
useAuthStore.subscribe((state, previous) => {
  if (
    authVersion !== getAuthSessionVersion() ||
    state.user?.id !== previous.user?.id ||
    state.user?.role !== previous.user?.role ||
    state.isAuthenticated !== previous.isAuthenticated
  ) {
    authVersion = getAuthSessionVersion()
    useExchangeSessionStore.getState().reset()
  }
})

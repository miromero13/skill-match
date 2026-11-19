import { beforeEach, expect, it, vi } from "vitest"
import { toast } from "sonner"
import { useAuthStore, type UserProfile } from "@/stores/auth-store"
import { useExchangeSessionStore as store } from "@/stores/exchange-session-store"
import * as service from "@/services/exchange-session-service"
import type { APIResponse } from "@/types/api"
import type {
  ExchangeSession,
  ExchangeSessionCreate,
  SessionListData,
} from "@/types/exchange-session"

vi.mock("@/services/exchange-session-service")
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }))

const member: UserProfile = {
  id: "learner",
  email: "learner@example.invalid",
  fullName: "Learner",
  role: "MEMBER",
  skillPointsBalance: 0,
  reputationScore: 0,
  trustLevel: 0,
  isVerified: false,
}

const session: ExchangeSession = {
  id: "session-1",
  match_id: "match-1",
  teaching_skill_id: "offer-1",
  created_by_id: "learner",
  instructor_id: "instructor",
  learner_id: "learner",
  starts_at: "2026-11-20T14:00:00Z",
  ends_at: "2026-11-20T15:00:00Z",
  timezone: "America/La_Paz",
  modality: "VIRTUAL",
  status: "PENDING",
  is_free: true,
  cancellation_reason: null,
  cancelled_by_id: null,
  cancelled_at: null,
  quota_restored: false,
  booking_blocked_until: null,
}

const createPayload: ExchangeSessionCreate = {
  match_id: session.match_id,
  teaching_skill_id: session.teaching_skill_id,
  instructor_id: session.instructor_id,
  starts_at: session.starts_at,
  ends_at: session.ends_at,
  timezone: session.timezone,
  modality: session.modality,
}

const response = <T>(data: T, message = "Servidor"): APIResponse<T> => ({
  statuscode: 200,
  message,
  data,
})

const listData: SessionListData = {
  items: [session],
  free_sessions_left: 1,
  free_sessions_limit: 2,
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

beforeEach(() => {
  vi.resetAllMocks()
  useAuthStore.getState().login(member, "access", "refresh")
  store.getState().reset()
  vi.mocked(service.getExchangeSessions).mockResolvedValue({
    ...response(listData, "Sesiones consultadas correctamente."),
    count: 1,
  })
})

it("loads sessions and the authenticated learner weekly quota", async () => {
  await store.getState().load()
  expect(store.getState()).toMatchObject({
    items: [session],
    total: 1,
    freeSessionsLeft: 1,
    freeSessionsLimit: 2,
    loading: false,
  })
})

it("creates the ratified payload and displays the exact backend message", async () => {
  vi.mocked(service.createExchangeSession).mockResolvedValue(
    response(session, "Sesión propuesta correctamente.")
  )
  expect(await store.getState().create(createPayload)).toBe(true)
  expect(service.createExchangeSession).toHaveBeenCalledWith(createPayload)
  expect(toast.success).toHaveBeenCalledWith("Sesión propuesta correctamente.")
})

it("cancels with a mandatory reason and reconciles quota", async () => {
  const cancelled = {
    ...session,
    status: "CANCELLED" as const,
    cancellation_reason: "Imprevisto familiar",
    quota_restored: true,
  }
  store.setState({ items: [session], freeSessionsLeft: 1 })
  vi.mocked(service.cancelExchangeSession).mockResolvedValue(
    response(cancelled, "Sesión cancelada y cupo restaurado.")
  )
  expect(await store.getState().cancel(session.id, "Imprevisto familiar")).toBe(
    true
  )
  expect(store.getState()).toMatchObject({
    items: [cancelled],
    freeSessionsLeft: 2,
  })
  expect(toast.success).toHaveBeenCalledWith(
    "Sesión cancelada y cupo restaurado."
  )
})

it.each([
  ["ACCEPTED" as const, service.acceptExchangeSession],
  ["REJECTED" as const, service.rejectExchangeSession],
])(
  "applies %s only through its explicit service action",
  async (status, action) => {
    const changed = { ...session, status }
    vi.mocked(action).mockResolvedValue(
      response(changed, `Sesión ${status.toLowerCase()}.`)
    )
    store.setState({ items: [session] })
    const operation = status === "ACCEPTED" ? "accept" : "reject"
    expect(await store.getState()[operation](session.id)).toBe(true)
    expect(store.getState().items[0]?.status).toBe(status)
    expect(toast.success).toHaveBeenCalledWith(
      `Sesión ${status.toLowerCase()}.`
    )
  }
)

it("reprograms and returns an accepted session to pending", async () => {
  const schedule = {
    starts_at: "2026-11-27T14:00:00Z",
    ends_at: "2026-11-27T15:00:00Z",
  }
  const changed: ExchangeSession = {
    ...session,
    ...schedule,
    status: "PENDING",
  }
  store.setState({ items: [{ ...session, status: "ACCEPTED" }] })
  vi.mocked(service.rescheduleExchangeSession).mockResolvedValue(
    response(changed, "Sesión reprogramada; espera confirmación.")
  )
  expect(await store.getState().reschedule(session.id, schedule)).toBe(true)
  expect(service.rescheduleExchangeSession).toHaveBeenCalledWith(
    session.id,
    schedule
  )
  expect(store.getState().items[0]).toMatchObject(changed)
})

it("prevents double submission for the same mutation", async () => {
  const pending = deferred<APIResponse<ExchangeSession>>()
  vi.mocked(service.createExchangeSession).mockReturnValue(pending.promise)
  const first = store.getState().create(createPayload)
  const second = store.getState().create(createPayload)
  expect(service.createExchangeSession).toHaveBeenCalledTimes(1)
  expect(await second).toBe(false)
  pending.resolve(response(session, "Sesión propuesta correctamente."))
  expect(await first).toBe(true)
})

it("keeps a confirmed mutation when an older list response arrives later", async () => {
  const pendingList = deferred<
    APIResponse<SessionListData> & { count: number }
  >()
  vi.mocked(service.getExchangeSessions).mockReturnValue(pendingList.promise)
  vi.mocked(service.createExchangeSession).mockResolvedValue(
    response(session, "Sesión propuesta correctamente.")
  )
  const loading = store.getState().load()
  expect(await store.getState().create(createPayload)).toBe(true)
  pendingList.resolve({
    ...response({ ...listData, items: [] }),
    count: 0,
  })
  await loading
  expect(store.getState().items).toEqual([session])
})

it("does not restore quota twice when a completed cancellation is retried", async () => {
  const cancelled: ExchangeSession = {
    ...session,
    status: "CANCELLED",
    cancellation_reason: "Imprevisto familiar",
    quota_restored: true,
  }
  store.setState({ items: [session], freeSessionsLeft: 1 })
  vi.mocked(service.cancelExchangeSession).mockResolvedValue(
    response(cancelled, "Sesión cancelada correctamente.")
  )
  expect(await store.getState().cancel(session.id, "Imprevisto familiar")).toBe(
    true
  )
  expect(await store.getState().cancel(session.id, "Imprevisto familiar")).toBe(
    true
  )
  expect(store.getState().freeSessionsLeft).toBe(2)
})

it("discards a slow private response after logout", async () => {
  const pending = deferred<APIResponse<SessionListData> & { count: number }>()
  vi.mocked(service.getExchangeSessions).mockReturnValue(pending.promise)
  const request = store.getState().load()
  useAuthStore.getState().logout()
  pending.resolve({ ...response(listData), count: 1 })
  await request
  expect(store.getState()).toMatchObject({
    items: [],
    total: 0,
    freeSessionsLeft: 0,
    loading: false,
  })
})

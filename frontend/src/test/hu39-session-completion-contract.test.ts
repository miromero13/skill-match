import { beforeEach, describe, expect, it, vi } from "vitest"
import { toast } from "sonner"
import { useAuthStore, type UserProfile } from "@/stores/auth-store"
import { useExchangeSessionStore as store } from "@/stores/exchange-session-store"
import * as service from "@/services/exchange-session-service"
import type { APIResponse } from "@/types/api"
import type {
  ExchangeSession,
  SessionConfirmRequest,
  SessionConfirmResponse,
  SessionNoShowRequest,
  SessionNoShowResponse,
} from "@/types/exchange-session"

vi.mock("@/services/exchange-session-service")
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }))

const member: UserProfile = {
  id: "learner-hu39",
  email: "learner@example.invalid",
  fullName: "Learner HU-39",
  role: "MEMBER",
  skillPointsBalance: 10,
  reputationScore: 5.0,
  trustLevel: 5,
  isVerified: true,
}

const acceptedSession: ExchangeSession = {
  id: "session-hu39-1",
  match_id: "match-1",
  teaching_skill_id: "offer-1",
  created_by_id: "learner-hu39",
  instructor_id: "instructor-hu39",
  learner_id: "learner-hu39",
  starts_at: "2026-11-20T14:00:00Z",
  ends_at: "2026-11-20T15:00:00Z",
  timezone: "America/La_Paz",
  modality: "VIRTUAL",
  status: "ACCEPTED",
  is_free: true,
  cancellation_reason: null,
  cancelled_by_id: null,
  cancelled_at: null,
  quota_restored: false,
  booking_blocked_until: null,
  actual_minutes: null,
  completed_at: null,
}

const response = <T>(data: T, message = "Operación completada exitosamente"): APIResponse<T> => ({
  statuscode: 200,
  message,
  data,
})

describe("HU-39 Session Completion Contract & Store (TDD - Red Phase)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useAuthStore.setState({
      user: member,
      token: "valid-token",
      isAuthenticated: true,
      isLoading: false,
    })
    store.getState().reset()
    store.setState({ items: [acceptedSession], total: 1, loaded: true })
  })

  it("calls confirmExchangeSession service and updates store on first confirmation", async () => {
    const confirmPayload: SessionConfirmRequest = {
      request_key: "00000000-0000-4000-8000-000000000001",
      actual_minutes: 60,
      topics: ["Arquitectura Hexagonal", "FastAPI"],
    }

    const firstConfirmationResult: SessionConfirmResponse = {
      session_id: acceptedSession.id,
      status: "ACCEPTED",
      my_confirmation: true,
      counterpart_confirmation: false,
      actual_minutes: 60,
      completed_at: null,
      escrow_release: "NOT_APPLICABLE",
    }

    vi.mocked(service.confirmExchangeSession).mockResolvedValueOnce(
      response(firstConfirmationResult, "Primera confirmación registrada.")
    )

    const success = await store.getState().confirmSession(acceptedSession.id, confirmPayload)

    expect(success).toBe(true)
    expect(service.confirmExchangeSession).toHaveBeenCalledWith(acceptedSession.id, confirmPayload)
    expect(toast.success).toHaveBeenCalledWith("Primera confirmación registrada.")
  })

  it("transitions session to COMPLETED in store on second matching confirmation", async () => {
    const confirmPayload: SessionConfirmRequest = {
      request_key: "00000000-0000-4000-8000-000000000002",
      actual_minutes: 60,
      topics: ["Arquitectura Hexagonal", "FastAPI"],
    }

    const completionResult: SessionConfirmResponse = {
      session_id: acceptedSession.id,
      status: "COMPLETED",
      my_confirmation: true,
      counterpart_confirmation: true,
      actual_minutes: 60,
      completed_at: "2026-11-20T15:05:00Z",
      escrow_release: "NOT_APPLICABLE",
    }

    vi.mocked(service.confirmExchangeSession).mockResolvedValueOnce(
      response(completionResult, "Sesión completada exitosamente.")
    )

    const success = await store.getState().confirmSession(acceptedSession.id, confirmPayload)

    expect(success).toBe(true)
    const updated = store.getState().items.find((s) => s.id === acceptedSession.id)
    expect(updated?.status).toBe("COMPLETED")
    expect(updated?.actual_minutes).toBe(60)
    expect(updated?.completed_at).toBe("2026-11-20T15:05:00Z")
  })

  it("calls reportSessionNoShow service and displays backend message", async () => {
    const noShowPayload: SessionNoShowRequest = {
      request_key: "00000000-0000-4000-8000-000000000003",
      reason: "La contraparte no se presentó a la sesión acordada.",
    }

    const noShowResult: SessionNoShowResponse = {
      session_id: acceptedSession.id,
      reported_by_id: member.id,
      absent_user_id: acceptedSession.instructor_id,
      reason: noShowPayload.reason,
      status: "PENDING_REPUTATION",
      reported_at: "2026-11-20T15:10:00Z",
    }

    vi.mocked(service.reportSessionNoShow).mockResolvedValueOnce(
      response(noShowResult, "Reporte de inasistencia registrado correctamente.")
    )

    const success = await store.getState().reportNoShow(acceptedSession.id, noShowPayload)

    expect(success).toBe(true)
    expect(service.reportSessionNoShow).toHaveBeenCalledWith(acceptedSession.id, noShowPayload)
    expect(toast.success).toHaveBeenCalledWith("Reporte de inasistencia registrado correctamente.")
  })
})

import { beforeEach, expect, it, vi } from "vitest"

import { apiClient } from "@/services/api-client"
import * as service from "@/services/exchange-session-service"

vi.mock("@/services/api-client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
  },
}))

const options = { showToastOnError: true, showToastOnSuccess: false }

beforeEach(() => vi.clearAllMocks())

it("uses the five ratified HU-38 operations and encodes the resource id", async () => {
  vi.mocked(apiClient.get).mockResolvedValue({
    statuscode: 200,
    message: "Sesiones recuperadas.",
    data: { items: [], free_sessions_left: 2, free_sessions_limit: 2 },
    count: 0,
  })
  await service.getExchangeSessions(2, 10)
  await service.createExchangeSession({
    match_id: "match",
    teaching_skill_id: "offer",
    instructor_id: "instructor",
    starts_at: "2026-11-20T18:00:00Z",
    ends_at: "2026-11-20T19:00:00Z",
    timezone: "America/La_Paz",
    modality: "VIRTUAL",
  })
  await service.acceptExchangeSession("session/a")
  await service.rejectExchangeSession("session/a")
  await service.rescheduleExchangeSession("session/a", {
    starts_at: "2026-11-27T18:00:00Z",
    ends_at: "2026-11-27T19:00:00Z",
  })
  await service.cancelExchangeSession("session/a", "Imprevisto familiar válido")
  await service.getSessionCalendarExport("session/a")

  expect(apiClient.get).toHaveBeenCalledWith("/sessions", {
    ...options,
    params: { page: 2, page_size: 10 },
  })
  expect(apiClient.patch).toHaveBeenCalledWith(
    "/sessions/session%2Fa/status",
    { status: "ACCEPTED" },
    options
  )
  expect(apiClient.patch).toHaveBeenCalledWith(
    "/sessions/session%2Fa/status",
    { status: "REJECTED" },
    options
  )
  expect(apiClient.put).toHaveBeenCalledWith(
    "/sessions/session%2Fa/reschedule",
    {
      starts_at: "2026-11-27T18:00:00Z",
      ends_at: "2026-11-27T19:00:00Z",
    },
    options
  )
  expect(apiClient.post).toHaveBeenLastCalledWith(
    "/sessions/session%2Fa/cancel",
    { cancellation_reason: "Imprevisto familiar válido" },
    options
  )
  expect(apiClient.get).toHaveBeenLastCalledWith(
    "/sessions/session%2Fa/calendar-export",
    options
  )
})

it("rejects a list response without a valid envelope count", async () => {
  vi.mocked(apiClient.get).mockResolvedValue({
    statuscode: 200,
    message: "Sesiones recuperadas.",
    data: { items: [], free_sessions_left: 2, free_sessions_limit: 2 },
  })
  await expect(service.getExchangeSessions()).rejects.toThrow(
    "La respuesta no contiene un total de sesiones válido."
  )
})

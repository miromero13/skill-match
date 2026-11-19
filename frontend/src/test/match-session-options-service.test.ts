import { beforeEach, expect, it, vi } from "vitest"

import { apiClient } from "@/services/api-client"
import { getMatchSessionOptions } from "@/services/match-service"

vi.mock("@/services/api-client", () => ({
  apiClient: { get: vi.fn() },
}))

beforeEach(() => vi.clearAllMocks())

it("requests the productive session options contract with an encoded match id", async () => {
  vi.mocked(apiClient.get).mockResolvedValue({
    statuscode: 200,
    message: "Opciones de agendamiento recuperadas exitosamente.",
    data: {
      match_id: "match/a",
      timezone: "America/La_Paz",
      horizon_days: 14,
      booking_blocked_until: null,
      directions: [],
    },
  })
  const controller = new AbortController()

  await getMatchSessionOptions("match/a", controller.signal)

  expect(apiClient.get).toHaveBeenCalledWith(
    "/matches/match%2Fa/session-options",
    { signal: controller.signal }
  )
})

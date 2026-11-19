import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, expect, it, vi } from "vitest"

import { MatchSessionBooking } from "@/components/sessions/match-session-booking"
import { getMatchSessionOptions } from "@/services/match-service"
import { useExchangeSessionStore } from "@/stores/exchange-session-store"

vi.mock("@/services/match-service", () => ({
  getMatchSessionOptions: vi.fn(),
}))

const create = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
  useExchangeSessionStore.setState({ pending: {}, create })
  vi.mocked(getMatchSessionOptions).mockResolvedValue({
    statuscode: 200,
    message: "Opciones recuperadas.",
    data: {
      match_id: "match-1",
      timezone: "America/La_Paz",
      horizon_days: 14,
      booking_blocked_until: null,
      directions: [
        {
          instructor_id: "instructor-1",
          instructor_name: "Sofía",
          learner_id: "learner-1",
          teaching_skill_id: "skill-1",
          skill_name: "Guitarra",
          modalities: ["VIRTUAL"],
          common_slots: [
            {
              starts_at: "2026-11-20T18:00:00Z",
              ends_at: "2026-11-20T19:00:00Z",
              timezone: "America/La_Paz",
              modality: "VIRTUAL",
              duration_minutes: 60,
            },
          ],
        },
      ],
    },
  })
})

it("loads canonical options and creates a session with backend identifiers", async () => {
  const user = userEvent.setup()
  create.mockResolvedValue(true)

  render(
    <MemoryRouter>
      <MatchSessionBooking matchId="match-1" />
    </MemoryRouter>
  )

  expect(await screen.findByText("Guitarra")).toBeInTheDocument()
  expect(getMatchSessionOptions).toHaveBeenCalledWith(
    "match-1",
    expect.any(AbortSignal)
  )
  await user.click(screen.getByRole("button", { name: "Agendar sesión" }))

  expect(create).toHaveBeenCalledWith({
    match_id: "match-1",
    teaching_skill_id: "skill-1",
    instructor_id: "instructor-1",
    starts_at: "2026-11-20T18:00:00Z",
    ends_at: "2026-11-20T19:00:00Z",
    timezone: "America/La_Paz",
    modality: "VIRTUAL",
  })
  expect(
    await screen.findByText("Sesión propuesta correctamente")
  ).toBeInTheDocument()
})

it("prevents a duplicate submit while creation is pending", async () => {
  let resolveCreate: (value: boolean) => void = () => undefined
  create.mockReturnValue(
    new Promise<boolean>((resolve) => {
      resolveCreate = resolve
    })
  )
  const user = userEvent.setup()

  render(
    <MemoryRouter>
      <MatchSessionBooking matchId="match-1" />
    </MemoryRouter>
  )

  const button = await screen.findByRole("button", { name: "Agendar sesión" })
  await user.click(button)
  await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
  expect(button).toBeDisabled()
  resolveCreate(true)
})

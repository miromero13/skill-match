import { beforeEach, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { SessionCard } from "@/components/sessions/session-card"
import { SessionsPage } from "@/pages/sessions-page"
import { useExchangeSessionStore as store } from "@/stores/exchange-session-store"
import * as sessionService from "@/services/exchange-session-service"
import type { ExchangeSession } from "@/types/exchange-session"

const baseSession: ExchangeSession = {
  id: "session-101",
  match_id: "match-1",
  teaching_skill_id: "skill-1",
  learner_id: "user-learner",
  instructor_id: "user-instructor",
  created_by_id: "user-learner",
  starts_at: "2026-11-20T14:00:00.000Z",
  ends_at: "2026-11-20T15:00:00.000Z",
  timezone: "UTC",
  modality: "VIRTUAL",
  status: "ACCEPTED",
  is_free: true,
  quota_restored: false,
  cancelled_at: null,
  cancelled_by_id: null,
  actual_minutes: null,
  completed_at: null,
  cancellation_reason: null,
  booking_blocked_until: null,
  can_confirm: false,
  can_report_noshow: false,
  my_confirmation: false,
  counterpart_confirmation: false,
}

beforeEach(() => {
  vi.restoreAllMocks()
  store.getState().reset()
})

it("renders COMPLETED badge and effective duration when session is completed", () => {
  const completedSession: ExchangeSession = {
    ...baseSession,
    status: "COMPLETED",
    actual_minutes: 45,
    completed_at: "2026-11-20T15:05:00.000Z",
  }

  render(
    <SessionCard
      session={completedSession}
      currentUserId="user-learner"
      onAccept={vi.fn()}
      onReject={vi.fn()}
      onReschedule={vi.fn()}
      onCancel={vi.fn()}
    />
  )

  expect(screen.getByText("Completada")).toBeInTheDocument()
  expect(
    screen.getByText(
      /Sesión completada y confirmada por ambas partes\. Duración efectiva: 45 minutos\./
    )
  ).toBeInTheDocument()
})

it("displays waiting alert when current user confirmed and counterpart has not", () => {
  const waitingSession: ExchangeSession = {
    ...baseSession,
    status: "ACCEPTED",
    can_confirm: false,
    my_confirmation: true,
    counterpart_confirmation: false,
  }

  render(
    <SessionCard
      session={waitingSession}
      currentUserId="user-learner"
      onAccept={vi.fn()}
      onReject={vi.fn()}
      onReschedule={vi.fn()}
      onCancel={vi.fn()}
    />
  )

  expect(
    screen.getByText(
      /Has registrado tu confirmación\. Esperando la confirmación de la contraparte para completarla\./
    )
  ).toBeInTheDocument()
})

it("allows confirming a virtual session with valid actual minutes", async () => {
  const user = userEvent.setup()
  const confirmSessionMock = vi.fn().mockResolvedValue(true)
  store.setState({ confirmSession: confirmSessionMock })

  const confirmableSession: ExchangeSession = {
    ...baseSession,
    status: "ACCEPTED",
    can_confirm: true,
  }

  render(
    <SessionCard
      session={confirmableSession}
      currentUserId="user-learner"
      onAccept={vi.fn()}
      onReject={vi.fn()}
      onReschedule={vi.fn()}
      onCancel={vi.fn()}
    />
  )

  const confirmTrigger = screen.getByRole("button", { name: "Confirmar sesión" })
  expect(confirmTrigger).toBeInTheDocument()
  await user.click(confirmTrigger)

  expect(screen.getByText("Confirmación de sesión realizada")).toBeInTheDocument()

  // Select 45m preset
  await user.click(screen.getByRole("button", { name: "45m" }))

  const submitBtn = screen.getByRole("button", { name: "Confirmar intercambio" })
  await user.click(submitBtn)

  expect(confirmSessionMock).toHaveBeenCalledWith(
    "session-101",
    expect.objectContaining({
      actual_minutes: 45,
      presence_pin: undefined,
    })
  )
})

it("validates 4-digit PIN requirement for in-person session confirmation", async () => {
  const user = userEvent.setup()
  const confirmSessionMock = vi.fn().mockResolvedValue(true)
  store.setState({ confirmSession: confirmSessionMock })

  const inPersonSession: ExchangeSession = {
    ...baseSession,
    modality: "PRESENCIAL",
    status: "ACCEPTED",
    can_confirm: true,
  }

  render(
    <SessionCard
      session={inPersonSession}
      currentUserId="user-learner"
      onAccept={vi.fn()}
      onReject={vi.fn()}
      onReschedule={vi.fn()}
      onCancel={vi.fn()}
    />
  )

  await user.click(screen.getByRole("button", { name: "Confirmar sesión" }))

  // Try to submit without PIN
  await user.click(screen.getByRole("button", { name: "Confirmar intercambio" }))
  expect(
    await screen.findByText("Debes ingresar el PIN de presencia de 4 dígitos proporcionado por la contraparte.")
  ).toBeInTheDocument()
  expect(confirmSessionMock).not.toHaveBeenCalled()

  // Enter valid 4-digit PIN
  const pinInput = screen.getByLabelText("PIN presencial de la contraparte")
  await user.type(pinInput, "1234")

  await user.click(screen.getByRole("button", { name: "Confirmar intercambio" }))
  expect(confirmSessionMock).toHaveBeenCalledWith(
    "session-101",
    expect.objectContaining({
      actual_minutes: 60,
      presence_pin: "1234",
    })
  )
})

it("opens Presence PIN modal and displays the 4-digit PIN for in-person sessions", async () => {
  const user = userEvent.setup()
  vi.spyOn(sessionService, "getSessionPresencePin").mockResolvedValue({
    statuscode: 200,
    message: "PIN presencial obtenido",
    data: {
      session_id: "session-101",
      presence_pin: "8492",
      expires_at: "2026-11-21T15:00:00.000Z",
      attempt_count: 0,
      is_locked: false,
    },
  })

  const inPersonSession: ExchangeSession = {
    ...baseSession,
    modality: "PRESENCIAL",
    status: "ACCEPTED",
  }

  render(
    <SessionCard
      session={inPersonSession}
      currentUserId="user-learner"
      onAccept={vi.fn()}
      onReject={vi.fn()}
      onReschedule={vi.fn()}
      onCancel={vi.fn()}
    />
  )

  const pinTrigger = screen.getByRole("button", { name: "Mi PIN presencial" })
  expect(pinTrigger).toBeInTheDocument()
  await user.click(pinTrigger)

  expect(screen.getByText("Tu PIN de presencia")).toBeInTheDocument()
  await waitFor(() => {
    expect(screen.getByText("8492")).toBeInTheDocument()
  })
})

it("allows reporting a no-show with validation on minimum reason length", async () => {
  const user = userEvent.setup()
  const reportNoShowMock = vi.fn().mockResolvedValue(true)
  store.setState({ reportNoShow: reportNoShowMock })

  const noShowEligibleSession: ExchangeSession = {
    ...baseSession,
    status: "ACCEPTED",
    can_report_noshow: true,
  }

  render(
    <SessionCard
      session={noShowEligibleSession}
      currentUserId="user-learner"
      onAccept={vi.fn()}
      onReject={vi.fn()}
      onReschedule={vi.fn()}
      onCancel={vi.fn()}
    />
  )

  const noShowTrigger = screen.getByRole("button", { name: "Reportar inasistencia" })
  expect(noShowTrigger).toBeInTheDocument()
  await user.click(noShowTrigger)

  expect(screen.getByText("Reportar inasistencia injustificada")).toBeInTheDocument()

  // Try short reason (< 10 chars)
  const reasonInput = screen.getByLabelText("Motivo de la inasistencia")
  await user.type(reasonInput, "No vino")
  await user.click(screen.getByRole("button", { name: "Confirmar reporte" }))

  expect(
    await screen.findByText("El motivo de inasistencia debe tener entre 10 y 500 caracteres.")
  ).toBeInTheDocument()
  expect(reportNoShowMock).not.toHaveBeenCalled()

  // Provide valid reason
  await user.clear(reasonInput)
  await user.type(reasonInput, "La contraparte no se conectó tras 30 minutos de espera.")
  await user.click(screen.getByRole("button", { name: "Confirmar reporte" }))

  expect(reportNoShowMock).toHaveBeenCalledWith(
    "session-101",
    expect.objectContaining({
      reason: "La contraparte no se conectó tras 30 minutos de espera.",
    })
  )
})

it("renders Completadas tab on SessionsPage and filters completed sessions", async () => {
  const completedSession: ExchangeSession = {
    ...baseSession,
    id: "session-completed-1",
    status: "COMPLETED",
    actual_minutes: 55,
  }
  const acceptedSession: ExchangeSession = {
    ...baseSession,
    id: "session-accepted-1",
    status: "ACCEPTED",
  }

  store.setState({
    loaded: true,
    loading: false,
    items: [completedSession, acceptedSession],
    error: null,
  })

  render(<SessionsPage />)

  // Verify tab trigger exists
  const completedTab = screen.getByRole("tab", { name: "Completadas" })
  expect(completedTab).toBeInTheDocument()

  // Switch to Completadas tab
  const user = userEvent.setup()
  await user.click(completedTab)

  // Expect only completed session to be visible in this tab
  expect(screen.getByText("Referencia session-")).toBeInTheDocument()
  expect(screen.getByText("Completada")).toBeInTheDocument()
})

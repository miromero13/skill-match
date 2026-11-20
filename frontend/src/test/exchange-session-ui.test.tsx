import { beforeEach, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { SessionBookingForm } from "@/components/sessions/session-booking-form"
import { SessionQuotaWidget } from "@/components/sessions/session-quota-widget"
import { SessionsPage } from "@/pages/sessions-page"
import { useExchangeSessionStore as store } from "@/stores/exchange-session-store"

beforeEach(() => {
  vi.restoreAllMocks()
  store.getState().reset()
})

it("renders the ratified X/2 quota copy", () => {
  render(<SessionQuotaWidget freeSessionsLeft={1} freeSessionsLimit={2} />)
  expect(
    screen.getByText(
      "Sesiones gratuitas restantes esta semana: 1/2 (máx. 1h c/u)"
    )
  ).toBeInTheDocument()
})

it("uses accessible Shadcn-backed controls and rejects sessions over 60 minutes", async () => {
  const user = userEvent.setup()
  const submit = vi.fn()
  render(
    <SessionBookingForm
      matchId="match-1"
      teachingSkillId="offer-1"
      instructorId="instructor-1"
      timezone="America/La_Paz"
      onSubmit={submit}
    />
  )
  await user.type(screen.getByLabelText("Inicio"), "2026-11-20T14:00")
  await user.type(screen.getByLabelText("Fin"), "2026-11-20T15:30")
  await user.click(screen.getByRole("button", { name: "Agendar sesión" }))
  expect(
    await screen.findByText("La sesión debe durar entre 1 y 60 minutos.")
  ).toBeInTheDocument()
  expect(submit).not.toHaveBeenCalled()
})

it("submits the canonical modality and ratified identifiers", async () => {
  const user = userEvent.setup()
  const submit = vi.fn().mockResolvedValue(true)
  render(
    <SessionBookingForm
      matchId="match-1"
      teachingSkillId="offer-1"
      instructorId="instructor-1"
      timezone="America/La_Paz"
      onSubmit={submit}
    />
  )
  await user.type(screen.getByLabelText("Inicio"), "2026-11-20T14:00")
  await user.type(screen.getByLabelText("Fin"), "2026-11-20T15:00")
  await user.click(screen.getByRole("combobox", { name: "Modalidad" }))
  await user.click(screen.getByRole("option", { name: "Virtual" }))
  await user.click(screen.getByRole("button", { name: "Agendar sesión" }))
  expect(submit).toHaveBeenCalledWith({
    match_id: "match-1",
    teaching_skill_id: "offer-1",
    instructor_id: "instructor-1",
    starts_at: "2026-11-20T18:00:00.000Z",
    ends_at: "2026-11-20T19:00:00.000Z",
    timezone: "America/La_Paz",
    modality: "VIRTUAL",
    payment_method: "FREE",
  })
})

it("shows loading without leaking stale session rows", () => {
  store.setState({ loading: true, items: [] })
  render(<SessionsPage />)
  expect(
    screen.getByRole("status", { name: "Cargando sesiones" })
  ).toBeInTheDocument()
  expect(
    screen.queryByText("No tienes sesiones programadas.")
  ).not.toBeInTheDocument()
})

it("shows the empty state after a completed load", () => {
  store.setState({ loading: false, loaded: true, items: [], error: null })
  render(<SessionsPage />)
  expect(
    screen.getByText("No tienes sesiones programadas.")
  ).toBeInTheDocument()
})

it("shows the exact backend error and retries", async () => {
  const user = userEvent.setup()
  const load = vi.fn().mockResolvedValue(undefined)
  store.setState({
    loading: false,
    loaded: true,
    items: [],
    error: "No fue posible consultar tus sesiones.",
    load,
  })
  render(<SessionsPage />)
  expect(screen.getByRole("alert")).toHaveTextContent(
    "No fue posible consultar tus sesiones."
  )
  await user.click(screen.getByRole("button", { name: "Reintentar" }))
  expect(load).toHaveBeenCalledTimes(1)
})

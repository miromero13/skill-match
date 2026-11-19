import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, expect, it, vi } from "vitest"

import { SessionCard } from "@/components/sessions/session-card"
import { getSessionCalendarExport } from "@/services/exchange-session-service"
import type { ExchangeSession } from "@/types/exchange-session"

vi.mock("@/services/exchange-session-service", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/services/exchange-session-service")>()),
  getSessionCalendarExport: vi.fn(),
}))

const accepted: ExchangeSession = {
  id: "session-1",
  match_id: "match-1",
  teaching_skill_id: "skill-1",
  created_by_id: "learner-1",
  instructor_id: "instructor-1",
  learner_id: "learner-1",
  starts_at: "2026-12-01T18:00:00Z",
  ends_at: "2026-12-01T19:00:00Z",
  timezone: "America/La_Paz",
  modality: "VIRTUAL",
  status: "ACCEPTED",
  is_free: true,
  cancellation_reason: null,
  cancelled_by_id: null,
  cancelled_at: null,
  quota_restored: false,
  booking_blocked_until: null,
}

const actions = {
  onAccept: vi.fn(),
  onReject: vi.fn(),
  onReschedule: vi.fn(),
  onCancel: vi.fn(),
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(getSessionCalendarExport).mockResolvedValue({
    statuscode: 200,
    message: "Exportación de calendario generada correctamente.",
    data: {
      filename: "skillmatch-session-session-1.ics",
      content_type: "text/calendar; charset=utf-8",
      ics_content: "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n",
      google_calendar_url: "https://calendar.google.com/calendar/render?action=TEMPLATE",
    },
  })
})

it("shows calendar export only for accepted sessions and loads it once", async () => {
  const user = userEvent.setup()
  const { rerender } = render(<SessionCard session={accepted} {...actions} />)

  await user.click(screen.getByRole("button", { name: "Añadir al calendario" }))
  expect(
    await screen.findByText("Exportación de calendario generada correctamente.")
  ).toBeInTheDocument()
  expect(getSessionCalendarExport).toHaveBeenCalledWith(
    "session-1",
    expect.any(AbortSignal)
  )
  expect(screen.getByRole("button", { name: "Descargar .ics" })).toBeEnabled()
  expect(screen.getByRole("button", { name: "Abrir Google Calendar" })).toBeEnabled()

  await user.click(screen.getByRole("button", { name: "Cerrar" }))
  rerender(<SessionCard session={{ ...accepted, status: "PENDING" }} {...actions} />)
  expect(screen.queryByRole("button", { name: "Añadir al calendario" })).not.toBeInTheDocument()
})

it("prevents duplicate loading while the export request is pending", async () => {
  let resolveRequest: (value: Awaited<ReturnType<typeof getSessionCalendarExport>>) => void =
    () => undefined
  vi.mocked(getSessionCalendarExport).mockReturnValue(
    new Promise((resolve) => {
      resolveRequest = resolve
    })
  )
  const user = userEvent.setup()
  render(<SessionCard session={accepted} {...actions} />)

  await user.click(screen.getByRole("button", { name: "Añadir al calendario" }))
  expect(await screen.findByRole("status", { name: "Preparando calendario" })).toBeVisible()
  expect(getSessionCalendarExport).toHaveBeenCalledTimes(1)
  resolveRequest({
    statuscode: 200,
    message: "Exportación lista.",
    data: {
      filename: "session.ics",
      content_type: "text/calendar; charset=utf-8",
      ics_content: "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n",
      google_calendar_url: "https://calendar.google.com/calendar/render?action=TEMPLATE",
    },
  })
})

it("downloads the ics blob and opens only the backend Google URL", async () => {
  const createObjectURL = vi.fn(() => "blob:calendar")
  const revokeObjectURL = vi.fn()
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    value: createObjectURL,
  })
  Object.defineProperty(URL, "revokeObjectURL", {
    configurable: true,
    value: revokeObjectURL,
  })
  const anchorClick = vi
    .spyOn(HTMLAnchorElement.prototype, "click")
    .mockImplementation(() => undefined)
  const open = vi.spyOn(window, "open").mockImplementation(() => null)
  const user = userEvent.setup()
  render(<SessionCard session={accepted} {...actions} />)

  await user.click(screen.getByRole("button", { name: "Añadir al calendario" }))
  await user.click(await screen.findByRole("button", { name: "Descargar .ics" }))
  expect(createObjectURL).toHaveBeenCalledWith(expect.any(Blob))
  expect(anchorClick).toHaveBeenCalledTimes(1)
  expect(revokeObjectURL).toHaveBeenCalledWith("blob:calendar")

  await user.click(screen.getByRole("button", { name: "Abrir Google Calendar" }))
  expect(open).toHaveBeenCalledWith(
    "https://calendar.google.com/calendar/render?action=TEMPLATE",
    "_blank",
    "noopener,noreferrer"
  )
})

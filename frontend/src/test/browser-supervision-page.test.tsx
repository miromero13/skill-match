import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { MemoryRouter } from "react-router-dom"
import { BrowserSupervisionPage } from "@/pages/browser-supervision-page"
import { useAuthStore } from "@/stores/auth-store"
import * as api from "@/services/browser-supervision"

vi.mock("@/services/browser-supervision", async original => {
  const actual = await original<typeof import("@/services/browser-supervision")>()
  return {
    ...actual,
    startBrowserTrial: vi.fn(),
    readBrowserTrial: vi.fn(),
    trialAction: vi.fn(),
    sendBrowserIncidents: vi.fn(),
    readBrowserLedger: vi.fn(),
    sendAVWindow: vi.fn(),
  }
})

const trial: api.Trial = {
  id: "17008646-a5fd-42aa-9e60-4a42266fc6de",
  mode: "TRIAL",
  created_at: new Date().toISOString(),
  expires_at: new Date(Date.now() + 86400000).toISOString(),
  closed_at: null,
  lease_until: new Date(Date.now() + 20000).toISOString(),
  event_count: 0,
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  useAuthStore.setState({
    user: { id: "member", fullName: "Member", email: "member@example.test", role: "MEMBER" } as NonNullable<
      ReturnType<typeof useAuthStore.getState>["user"]
    >,
  })
  vi.mocked(api.startBrowserTrial).mockResolvedValue({
    trial,
    message: "Sesión de prueba preparada. No inicia un examen ni consume intentos.",
  })
  vi.mocked(api.trialAction).mockImplementation(async (_id, _tab, action) => ({
    trial: { ...trial, closed_at: action === "close" ? new Date().toISOString() : null },
    message: "Prueba cerrada. La bitácora se conserva.",
  }))
  vi.mocked(api.readBrowserLedger).mockResolvedValue({
    statuscode: 200,
    message: "Bitácora de prueba recuperada.",
    data: [],
    count: 0,
  })
  vi.mocked(api.sendBrowserIncidents).mockImplementation(async (_id, _tab, events) => ({
    accepted_ids: events.map(row => row.event_id),
    event_count: events.length,
  }))
  vi.mocked(api.sendAVWindow).mockResolvedValue({
    window_id: "window-123",
    face_count: 1,
    head_orientation: "CENTER",
    identity_match: true,
    speech_detected: false,
    noise_level: 0.02,
    anomalies: [],
    incidents_created: [],
  })
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

function show() {
  return render(
    <MemoryRouter>
      <BrowserSupervisionPage />
    </MemoryRouter>,
  )
}

async function activate() {
  fireEvent.click(screen.getByRole("checkbox", { name: /Acepto los controles/ }))
  fireEvent.click(screen.getByRole("button", { name: "Activar prueba" }))
  await waitFor(() => expect(screen.getByRole("textbox", { name: "Área supervisada" })).not.toBeDisabled())
}

it("does not start anything on mount, requires consent, records real dispatched actions and releases on exit", async () => {
  const view = show()
  expect(api.startBrowserTrial).not.toHaveBeenCalled()
  expect(screen.getByRole("button", { name: "Activar prueba" })).toBeDisabled()
  await activate()
  expect(screen.getByText("Sesión de prueba preparada. No inicia un examen ni consume intentos.")).toBeInTheDocument()
  const area = screen.getByRole("textbox", { name: "Área supervisada" })
  fireEvent.paste(area)
  await waitFor(() =>
    expect(api.sendBrowserIncidents).toHaveBeenCalledWith(
      trial.id,
      expect.any(String),
      expect.arrayContaining([expect.objectContaining({ kind: "PASTE" })]),
    ),
  )
  expect(screen.getByRole("status")).toHaveTextContent("Acción bloqueada dentro del área supervisada y registrada como incidente de prueba.")
  view.unmount()
  expect(api.trialAction).toHaveBeenCalledWith(trial.id, expect.any(String), "release", true)
})

it("shows the exact server conflict and keeps editor disabled", async () => {
  vi.mocked(api.startBrowserTrial).mockRejectedValue(new Error("Esta prueba está activa en otra pestaña."))
  show()
  fireEvent.click(screen.getByRole("checkbox", { name: /Acepto los controles/ }))
  fireEvent.click(screen.getByRole("button", { name: "Activar prueba" }))
  expect(await screen.findByRole("alert")).toHaveTextContent("Esta prueba está activa en otra pestaña.")
  expect(screen.getByRole("textbox", { name: "Área supervisada" })).toBeDisabled()
})

it("acknowledges pending incidents before closing and preserves the ledger", async () => {
  show()
  await activate()
  fireEvent.click(screen.getByRole("button", { name: "Cerrar prueba" }))
  expect(await screen.findByText("Prueba cerrada. La bitácora se conserva.")).toBeInTheDocument()
  expect(screen.getByRole("textbox", { name: "Área supervisada" })).toBeDisabled()
  expect(api.trialAction).toHaveBeenCalledWith(trial.id, expect.any(String), "close")
  expect(screen.getByRole("heading", { name: /Bitácora/ })).toBeInTheDocument()
})

it("restores a saved ledger without activating controls or sending incidents", async () => {
  localStorage.setItem("sm43:last:member", trial.id)
  vi.mocked(api.readBrowserTrial).mockResolvedValue(trial)
  show()
  expect(await screen.findByText(new RegExp(trial.id))).toBeInTheDocument()
  expect(api.readBrowserLedger).toHaveBeenCalledWith(trial.id, 0)
  expect(api.startBrowserTrial).not.toHaveBeenCalled()
  expect(api.sendBrowserIncidents).not.toHaveBeenCalled()
  expect(screen.getByRole("textbox", { name: "Área supervisada" })).toBeDisabled()
})

it("disables the area when server lease renewal fails and shows the exact message", async () => {
  vi.useFakeTimers()
  show()
  await act(async () => {
    fireEvent.click(screen.getByRole("checkbox", { name: /Acepto los controles/ }))
  })
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "Activar prueba" }))
  })
  expect(screen.getByRole("textbox", { name: "Área supervisada" })).not.toBeDisabled()
  vi.mocked(api.trialAction).mockRejectedValue(new Error("Esta prueba perdió su autorización."))
  await act(async () => {
    await vi.advanceTimersByTimeAsync(5000)
  })
  expect(screen.getByRole("textbox", { name: "Área supervisada" })).toBeDisabled()
  expect(screen.getByRole("alert")).toHaveTextContent("Esta prueba perdió su autorización.")
})

it("renders continuous audiovisual telemetry indicators and stops media tracks on close", async () => {
  const stopTrackMock = vi.fn()
  const mockStream = {
    getTracks: () => [
      { kind: "video", stop: stopTrackMock, addEventListener: vi.fn(), removeEventListener: vi.fn() },
      { kind: "audio", stop: stopTrackMock, addEventListener: vi.fn(), removeEventListener: vi.fn() },
    ],
  }

  // Mock getUserMedia
  Object.defineProperty(navigator, "mediaDevices", {
    value: {
      getUserMedia: vi.fn().mockResolvedValue(mockStream),
    },
    configurable: true,
  })

  show()
  expect(screen.getByText("Supervisión audiovisual continua en vivo")).toBeInTheDocument()
  expect(screen.getByText("Presencia facial")).toBeInTheDocument()
  expect(screen.getByText("Orientación de cabeza")).toBeInTheDocument()
  expect(screen.getByText("Cotejo con perfil")).toBeInTheDocument()
  expect(screen.getByText("Actividad acústica")).toBeInTheDocument()

  await activate()

  expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledWith(
    expect.objectContaining({ video: expect.any(Object), audio: expect.any(Object) }),
  )

  fireEvent.click(screen.getByRole("button", { name: "Cerrar prueba" }))
  await waitFor(() => expect(stopTrackMock).toHaveBeenCalledTimes(2))
})

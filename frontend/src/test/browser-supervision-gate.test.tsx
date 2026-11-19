import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { MemoryRouter } from "react-router-dom"
import { BrowserSupervisionPage } from "@/pages/browser-supervision-page"
import { useAuthStore } from "@/stores/auth-store"
import * as api from "@/services/browser-supervision"
import * as gaze from "@/services/gaze-tracking"
import { stubMedia } from "@/test/av-test-support"

vi.mock("@/services/browser-supervision", async (original) => {
  const actual = await original<typeof import("@/services/browser-supervision")>()
  return {
    ...actual,
    startBrowserTrial: vi.fn(), readBrowserTrial: vi.fn(), trialAction: vi.fn(), sendBrowserIncidents: vi.fn(),
    readBrowserLedger: vi.fn(), sendAVWindow: vi.fn(), calibrateGaze: vi.fn(), calibrateVoice: vi.fn(),
  }
})
vi.mock("@/services/gaze-tracking", async (original) => {
  const actual = await original<typeof import("@/services/gaze-tracking")>()
  return { ...actual, startFaceTracker: vi.fn() }
})

const zone: gaze.GazeZone = {
  pitch_min: -9, pitch_max: 13, yaw_min: -13, yaw_max: 13, gaze_h_min: -0.65, gaze_h_max: 0.65, gaze_v_min: -0.45, gaze_v_max: 0.55,
}
const unseeded: api.Trial = {
  id: "17008646-a5fd-42aa-9e60-4a42266fc6de", mode: "TRIAL", created_at: new Date().toISOString(),
  expires_at: new Date(Date.now() + 86_400_000).toISOString(), closed_at: null,
  lease_until: new Date(Date.now() + 20_000).toISOString(), event_count: 0, gaze_zone: null, voice_enrolled: false,
}
const seeded: api.Trial = { ...unseeded, gaze_zone: zone, voice_enrolled: true }
const trial = unseeded
const tracker = { setZone: vi.fn(), takeSamples: vi.fn(() => []), takeMouthSamples: vi.fn(() => []), stop: vi.fn() }

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  useAuthStore.setState({
    user: { id: "member", fullName: "Member", email: "member@example.test", role: "MEMBER" } as NonNullable<
      ReturnType<typeof useAuthStore.getState>["user"]
    >,
  })
  vi.mocked(gaze.startFaceTracker).mockResolvedValue(tracker)
  vi.mocked(api.startBrowserTrial).mockResolvedValue({ trial: unseeded, message: "Sesión de prueba preparada." })
  vi.mocked(api.trialAction).mockImplementation(async () => ({ trial, message: "ok" }))
  vi.mocked(api.readBrowserLedger).mockResolvedValue({ statuscode: 200, message: "ok", data: [], count: 0 })
  vi.mocked(api.sendBrowserIncidents).mockImplementation(async (_id, _tab, events) => ({
    accepted_ids: events.map((row) => row.event_id), event_count: events.length,
  }))
  vi.mocked(api.sendAVWindow).mockResolvedValue({
    window_id: "w", face_count: 1, head_orientation: "CENTER", identity_match: true, speech_detected: false,
    noise_level: 0.02, anomalies: [], incidents_created: [],
  })
})
afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

const show = () => render(<MemoryRouter><BrowserSupervisionPage /></MemoryRouter>)
const advance = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms) })
function press() {
  fireEvent.click(screen.getByRole("checkbox", { name: /Acepto los controles/ }))
  fireEvent.click(screen.getByRole("button", { name: "Activar prueba" }))
}
async function activate() {
  press()
  await waitFor(() => expect(screen.getByRole("textbox", { name: "Área supervisada" })).not.toBeDisabled())
  await waitFor(() => expect(gaze.startFaceTracker).toHaveBeenCalled())
}


const ticks = async (count: number) => { for (let index = 0; index < count; index++) await advance(400) }
const seed = (value: api.Trial) => vi.mocked(api.startBrowserTrial).mockResolvedValue({ trial: value, message: "Sesión de prueba preparada." })

async function calibrateGazeStep() {
  vi.mocked(api.calibrateGaze).mockResolvedValue({ result: { zone, frames_used: 15 }, message: "Zona de mirada calibrada." })
  fireEvent.click(screen.getByRole("button", { name: "Empezar calibración" }))
  await advance(15_000)
  expect(await screen.findByText("Zona de mirada calibrada.")).toBeInTheDocument()
}

async function readPhrase(media: ReturnType<typeof stubMedia>) {
  fireEvent.click(screen.getByRole("button", { name: /Empezar calibración de voz|Reintentar/ }))
  await advance(3000)
  media.feed(144_000, 0.1)
  await advance(7000)
}

it("blocks supervision until the gaze and the voice calibration both succeed, in order, with the camera on", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  const media = stubMedia()
  show()
  await activate()
  expect(screen.getByText("Cámara y audio activos")).toBeInTheDocument() // preview available while calibrating
  expect(screen.getByTestId("calibration-gate")).toHaveTextContent("Paso 1 de 2")
  expect(screen.getByTestId("gaze-calibration")).toBeInTheDocument()
  expect(screen.queryByTestId("voice-calibration")).not.toBeInTheDocument()
  await ticks(12)
  expect(api.sendAVWindow).not.toHaveBeenCalled()

  await calibrateGazeStep()
  expect(screen.getByTestId("calibration-gate")).toHaveTextContent("Paso 2 de 2")
  expect(screen.getByTestId("voice-calibration")).toBeInTheDocument()
  await ticks(12)
  expect(api.sendAVWindow).not.toHaveBeenCalled()

  vi.mocked(api.calibrateVoice).mockRejectedValueOnce(new Error("No se detectó voz suficiente. Repetí la lectura."))
  await readPhrase(media)
  expect(await screen.findByText("No se detectó voz suficiente. Repetí la lectura.")).toBeInTheDocument()
  await ticks(12)
  expect(api.sendAVWindow).not.toHaveBeenCalled() // a failed step keeps the gate closed

  vi.mocked(api.calibrateVoice).mockResolvedValue({ result: { voice_enrolled: true, voiced_seconds: 4 }, message: "Voz calibrada." })
  await readPhrase(media)
  expect(await screen.findByText("Voz calibrada.")).toBeInTheDocument()
  await ticks(8)
  expect(api.sendAVWindow).toHaveBeenCalled()
  expect(screen.getByTestId("calibration-gate")).toHaveTextContent("Calibración completa")
})

it("starts supervising at once when the server reports a zone and an enrolled voice (seeded trial)", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  stubMedia()
  seed(seeded)
  show()
  await activate()
  expect(screen.queryByTestId("calibration-gate")).not.toBeInTheDocument()
  expect(screen.queryByTestId("gaze-calibration")).not.toBeInTheDocument()
  await ticks(8)
  expect(api.sendAVWindow).toHaveBeenCalled()
})

it("keeps blocking when only the zone is seeded and asks for the voice", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  stubMedia()
  seed({ ...unseeded, gaze_zone: zone })
  show()
  await activate()
  expect(screen.getByTestId("calibration-gate")).toHaveTextContent("Paso 2 de 2")
  expect(screen.getByTestId("voice-calibration")).toBeInTheDocument()
  await ticks(12)
  expect(api.sendAVWindow).not.toHaveBeenCalled()
})

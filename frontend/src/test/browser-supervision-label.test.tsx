import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
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
    readBrowserLedger: vi.fn(), sendAVWindow: vi.fn(),
  }
})
vi.mock("@/services/gaze-tracking", async (original) => {
  const actual = await original<typeof import("@/services/gaze-tracking")>()
  return { ...actual, startFaceTracker: vi.fn() }
})

const zone: gaze.GazeZone = {
  pitch_min: -9, pitch_max: 13, yaw_min: -13, yaw_max: 13, gaze_h_min: -0.65, gaze_h_max: 0.65, gaze_v_min: -0.45, gaze_v_max: 0.55,
}
/** A trial seeded from a valid pre-exam calibration: supervision may start right away. */
const trial: api.Trial = {
  id: "17008646-a5fd-42aa-9e60-4a42266fc6de", mode: "TRIAL", created_at: new Date().toISOString(),
  expires_at: new Date(Date.now() + 86_400_000).toISOString(), closed_at: null,
  lease_until: new Date(Date.now() + 20_000).toISOString(), event_count: 0, gaze_zone: zone, voice_enrolled: true,
}
const manyGaze: gaze.GazeSampleDTO[] = Array.from({ length: 100 }, (_, index) => ({
  t_ms: index * 40, head_pitch: 0, head_yaw: 0, gaze_h: 0, gaze_v: 0, blink: false, face_count: 1, mouth_open: 0.1,
}))
const tracker = { setZone: vi.fn(), takeSamples: vi.fn(() => manyGaze), takeMouthSamples: vi.fn(() => []), stop: vi.fn() }

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  useAuthStore.setState({
    user: { id: "member", fullName: "Member", email: "member@example.test", role: "MEMBER" } as NonNullable<
      ReturnType<typeof useAuthStore.getState>["user"]
    >,
  })
  vi.mocked(gaze.startFaceTracker).mockResolvedValue(tracker)
  vi.mocked(api.startBrowserTrial).mockResolvedValue({ trial, message: "Sesión de prueba preparada." })
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
  vi.unstubAllEnvs()
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


const tick = () => advance(400)

const LABEL = { name: "Etiqueta de prueba" }
async function firstWindow() {
  const media = stubMedia()
  show()
  await activate()
  for (let index = 0; index < 8; index++) { media.feed(6400, 0.1); await tick() }
  return vi.mocked(api.sendAVWindow).mock.calls[0][1]
}

it("in DEV shows the test-label selector and sends the chosen label with each window", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
  const media = stubMedia()
  show()
  await activate()
  expect(screen.getByRole("combobox", LABEL)).toHaveTextContent("normal")
  await user.click(screen.getByRole("combobox", LABEL))
  await user.click(await screen.findByRole("option", { name: "mirando_abajo" }))
  expect(screen.getByRole("combobox", LABEL)).toHaveTextContent("mirando_abajo")
  for (let index = 0; index < 8; index++) { media.feed(6400, 0.1); await tick() }
  expect(vi.mocked(api.sendAVWindow).mock.calls[0][1].label).toBe("mirando_abajo")
})

it("in DEV a window carries the default label normal", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  expect((await firstWindow()).label).toBe("normal")
})

it("outside DEV there is no selector and no label is sent", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  vi.stubEnv("DEV", false)
  const window = await firstWindow()
  expect(screen.queryByRole("combobox", LABEL)).not.toBeInTheDocument()
  expect(window).not.toHaveProperty("label")
})

import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, expect, it, vi, type Mock } from "vitest"
import { MemoryRouter } from "react-router-dom"
import { BrowserSupervisionPage } from "@/pages/browser-supervision-page"
import { useAuthStore } from "@/stores/auth-store"
import * as api from "@/services/browser-supervision"
import * as gaze from "@/services/gaze-tracking"

vi.mock("@/services/browser-supervision", async (original) => {
  const actual = await original<typeof import("@/services/browser-supervision")>()
  return {
    ...actual,
    startBrowserTrial: vi.fn(),
    readBrowserTrial: vi.fn(),
    trialAction: vi.fn(),
    sendBrowserIncidents: vi.fn(),
    readBrowserLedger: vi.fn(),
    sendAVWindow: vi.fn(),
    calibrateGaze: vi.fn(),
  }
})
vi.mock("@/services/gaze-tracking", async (original) => {
  const actual = await original<typeof import("@/services/gaze-tracking")>()
  return { ...actual, startFaceTracker: vi.fn() }
})

const trial: api.Trial = {
  id: "17008646-a5fd-42aa-9e60-4a42266fc6de",
  mode: "TRIAL",
  created_at: new Date().toISOString(),
  expires_at: new Date(Date.now() + 86400000).toISOString(),
  closed_at: null,
  lease_until: new Date(Date.now() + 20000).toISOString(),
  event_count: 0,
  gaze_zone: null,
}
const zone: gaze.GazeZone = {
  pitch_min: -9,
  pitch_max: 13,
  yaw_min: -13,
  yaw_max: 13,
  gaze_h_min: -0.65,
  gaze_h_max: 0.65,
  gaze_v_min: -0.45,
  gaze_v_max: 0.55,
}

interface FakeTracker {
  setZone: Mock<gaze.FaceTracker["setZone"]>
  takeSamples: Mock<gaze.FaceTracker["takeSamples"]>
  stop: Mock<gaze.FaceTracker["stop"]>
}
const sample: gaze.GazeSampleDTO = {
  t_ms: 100,
  head_pitch: 1,
  head_yaw: -2,
  gaze_h: 0.1,
  gaze_v: -0.1,
  blink: false,
  face_count: 1,
}
let tracker: FakeTracker
let onAway: ((away: boolean) => void) | undefined

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  useAuthStore.setState({
    user: { id: "member", fullName: "Member", email: "member@example.test", role: "MEMBER" } as NonNullable<
      ReturnType<typeof useAuthStore.getState>["user"]
    >,
  })
  tracker = { setZone: vi.fn(), takeSamples: vi.fn(() => [sample]), stop: vi.fn() }
  onAway = undefined
  vi.mocked(gaze.startFaceTracker).mockImplementation(async (_video, options) => {
    onAway = options?.onAway
    return tracker
  })
  vi.mocked(api.startBrowserTrial).mockResolvedValue({ trial, message: "Sesión de prueba preparada." })
  vi.mocked(api.trialAction).mockImplementation(async (_id, _tab, action) => ({
    trial: { ...trial, closed_at: action === "close" ? new Date().toISOString() : null },
    message: "Prueba cerrada. La bitácora se conserva.",
  }))
  vi.mocked(api.readBrowserLedger).mockResolvedValue({ statuscode: 200, message: "ok", data: [], count: 0 })
  vi.mocked(api.sendBrowserIncidents).mockImplementation(async (_id, _tab, events) => ({
    accepted_ids: events.map((row) => row.event_id),
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

function stubCapture() {
  const stop = vi.fn()
  const stream = {
    getTracks: () => [
      { kind: "video", stop, addEventListener: vi.fn(), removeEventListener: vi.fn() },
      { kind: "audio", stop, addEventListener: vi.fn(), removeEventListener: vi.fn() },
    ],
  }
  Object.defineProperty(navigator, "mediaDevices", {
    value: { getUserMedia: vi.fn().mockResolvedValue(stream) },
    configurable: true,
  })
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined)
  Object.defineProperty(HTMLVideoElement.prototype, "videoWidth", { value: 640, configurable: true })
  Object.defineProperty(HTMLVideoElement.prototype, "videoHeight", { value: 480, configurable: true })
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({ drawImage: vi.fn() } as never)
  let counter = 0
  vi.spyOn(HTMLCanvasElement.prototype, "toDataURL").mockImplementation(() => `data:image/jpeg;base64,F${counter++}`)
  vi.stubGlobal(
    "AudioContext",
    class {
      sampleRate = 16000
      state = "running"
      destination = {}
      resume = () => Promise.resolve()
      close = () => Promise.resolve()
      createMediaStreamSource = () => ({ connect: vi.fn() })
      createAnalyser = () => ({ fftSize: 1024, connect: vi.fn(), getFloatTimeDomainData: vi.fn() })
      createScriptProcessor = () => ({ connect: vi.fn(), disconnect: vi.fn(), onaudioprocess: null })
    },
  )
}

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
  await waitFor(() => expect(gaze.startFaceTracker).toHaveBeenCalled())
}

async function runWindow() {
  for (let i = 0; i < 6; i++)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(400)
    })
}

it("attaches frame timestamps and browser telemetry to every audiovisual window", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  stubCapture()
  show()
  await activate()
  await runWindow()
  expect(api.sendAVWindow).toHaveBeenCalled()
  const payload = vi.mocked(api.sendAVWindow).mock.calls[0][1]
  expect(payload.frames.length).toBeGreaterThan(0)
  expect(payload.frame_times_ms).toHaveLength(payload.frames.length)
  const times = payload.frame_times_ms ?? []
  expect(times.every((value, index) => value >= 0 && value <= payload.duration_ms && (index === 0 || value >= times[index - 1]))).toBe(true)
  expect(payload.gaze_samples).toEqual([sample])
  // The tracker is asked for exactly the window the payload describes: from observed_at, for duration_ms.
  expect(tracker.takeSamples).toHaveBeenCalledWith(Date.parse(payload.observed_at), payload.duration_ms)
})

it("still sends windows without telemetry when browser tracking is unavailable and says so", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  stubCapture()
  vi.mocked(gaze.startFaceTracker).mockRejectedValue(new Error("assets missing"))
  show()
  fireEvent.click(screen.getByRole("checkbox", { name: /Acepto los controles/ }))
  fireEvent.click(screen.getByRole("button", { name: "Activar prueba" }))
  expect(await screen.findByText(/El seguimiento de mirada en tu navegador no está disponible/)).toBeInTheDocument()
  await runWindow()
  expect(api.sendAVWindow).toHaveBeenCalled()
  expect(vi.mocked(api.sendAVWindow).mock.calls[0][1].gaze_samples).toEqual([])
})

it("warns 'Mirá a la pantalla' while away without blocking anything, and clears it", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  stubCapture()
  show()
  await activate()
  expect(screen.queryByTestId("gaze-away")).not.toBeInTheDocument()
  act(() => onAway?.(true))
  expect(screen.getByTestId("gaze-away")).toHaveTextContent("Mirá a la pantalla")
  expect(screen.getByRole("textbox", { name: "Área supervisada" })).not.toBeDisabled()
  await runWindow()
  expect(api.sendAVWindow).toHaveBeenCalled() // the hint never stops the supervision
  act(() => onAway?.(false))
  expect(screen.queryByTestId("gaze-away")).not.toBeInTheDocument()
})

async function finishCalibration() {
  fireEvent.click(screen.getByRole("button", { name: "Empezar calibración" }))
  await act(async () => {
    await vi.advanceTimersByTimeAsync(15000) // 5 targets x (settle + 3 frames)
  })
}

it("calibrates the gaze zone through the reusable step and hands it to the tracker", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  stubCapture()
  vi.mocked(api.calibrateGaze).mockResolvedValue({
    result: { zone, frames_used: 15 },
    message: "Zona de mirada calibrada.",
  })
  show()
  await activate()
  expect(screen.getByTestId("gaze-calibration")).toBeInTheDocument()
  await finishCalibration()
  expect(screen.getByText("Zona de mirada calibrada.")).toBeInTheDocument()
  expect(api.calibrateGaze).toHaveBeenCalledTimes(1)
  const [id, tabId, points] = vi.mocked(api.calibrateGaze).mock.calls[0]
  expect(id).toBe(trial.id)
  expect(tabId).toEqual(expect.any(String))
  expect(points.map((point) => point.target)).toEqual(["CENTER", "TOP_LEFT", "TOP_RIGHT", "BOTTOM_LEFT", "BOTTOM_RIGHT"])
  expect(points.every((point) => point.frames.length === 3 && point.frames.every((frame) => frame.startsWith("data:image/jpeg")))).toBe(true)
  expect(tracker.setZone).toHaveBeenLastCalledWith(zone)
})

it("shows the exact server message when the calibration is rejected", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  stubCapture()
  const rejection = "No pudimos ver tu rostro en todos los puntos. Ubicate frente a la cámara con buena luz y repetí la calibración."
  vi.mocked(api.calibrateGaze).mockRejectedValue(new Error(rejection))
  show()
  await activate()
  await finishCalibration()
  expect(screen.getByText(rejection)).toBeInTheDocument()
  expect(tracker.setZone).not.toHaveBeenCalledWith(zone)
})

it("stops the browser tracker when the trial is closed and labels the new incidents in Spanish", async () => {
  stubCapture()
  show()
  await activate()
  fireEvent.click(screen.getByRole("button", { name: "Cerrar prueba" }))
  await waitFor(() => expect(tracker.stop).toHaveBeenCalled())
  vi.mocked(api.readBrowserLedger).mockResolvedValue({
    statuscode: 200,
    message: "ok",
    data: (["GAZE_AWAY", "HEAD_POSE_UP", "CLIENT_MISMATCH"] as const).map((kind, index) => ({
      event_id: `00000000-0000-4000-8000-00000000000${index}`,
      kind,
      observed_at: new Date().toISOString(),
      duration_ms: 1200,
      sequence: index + 1,
      received_at: new Date().toISOString(),
    })),
    count: 3,
  })
  cleanup()
  localStorage.setItem("sm43:last:member", trial.id)
  vi.mocked(api.readBrowserTrial).mockResolvedValue(trial)
  show()
  for (const label of [
    "Mirada fuera de la pantalla sostenida",
    "Cabeza orientada hacia arriba sostenida",
    "El navegador contradice la medición del servidor",
  ])
    expect(await screen.findByText(new RegExp(label))).toBeInTheDocument()
})

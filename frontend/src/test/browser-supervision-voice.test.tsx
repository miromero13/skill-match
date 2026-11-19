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
    calibrateVoice: vi.fn(),
  }
})
vi.mock("@/services/gaze-tracking", async (original) => {
  const actual = await original<typeof import("@/services/gaze-tracking")>()
  return { ...actual, startFaceTracker: vi.fn() }
})

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
const baseTrial: api.Trial = {
  id: "17008646-a5fd-42aa-9e60-4a42266fc6de",
  mode: "TRIAL",
  created_at: new Date().toISOString(),
  expires_at: new Date(Date.now() + 86400000).toISOString(),
  closed_at: null,
  lease_until: new Date(Date.now() + 20000).toISOString(),
  event_count: 0,
  gaze_zone: null,
  voice_enrolled: false,
}
const windowResult: api.AVWindowResponse = {
  window_id: "window-123",
  face_count: 1,
  head_orientation: "CENTER",
  identity_match: true,
  speech_detected: false,
  noise_level: 0.02,
  anomalies: [],
  incidents_created: [],
}

interface FakeTracker {
  setZone: Mock<gaze.FaceTracker["setZone"]>
  takeSamples: Mock<gaze.FaceTracker["takeSamples"]>
  takeMouthSamples: Mock<gaze.FaceTracker["takeMouthSamples"]>
  stop: Mock<gaze.FaceTracker["stop"]>
}
let tracker: FakeTracker
let processor: { onaudioprocess: ((event: unknown) => void) | null }

function useTrial(trial: api.Trial) {
  vi.mocked(api.startBrowserTrial).mockResolvedValue({ trial, message: "Sesión de prueba preparada." })
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  useAuthStore.setState({
    user: { id: "member", fullName: "Member", email: "member@example.test", role: "MEMBER" } as NonNullable<
      ReturnType<typeof useAuthStore.getState>["user"]
    >,
  })
  tracker = {
    setZone: vi.fn(),
    takeSamples: vi.fn(() => []),
    takeMouthSamples: vi.fn(() => [{ t_ms: 120, mouth_open: 0.2 }]),
    stop: vi.fn(),
  }
  vi.mocked(gaze.startFaceTracker).mockImplementation(async () => tracker)
  useTrial(baseTrial)
  vi.mocked(api.trialAction).mockImplementation(async (_id, _tab, action) => ({
    trial: { ...baseTrial, closed_at: action === "close" ? new Date().toISOString() : null },
    message: "Prueba cerrada. La bitácora se conserva.",
  }))
  vi.mocked(api.readBrowserLedger).mockResolvedValue({ statuscode: 200, message: "ok", data: [], count: 0 })
  vi.mocked(api.sendBrowserIncidents).mockImplementation(async (_id, _tab, events) => ({
    accepted_ids: events.map((row) => row.event_id),
    event_count: events.length,
  }))
  vi.mocked(api.sendAVWindow).mockResolvedValue(windowResult)
  vi.mocked(api.calibrateVoice).mockResolvedValue({
    result: { voice_enrolled: true, voiced_seconds: 4.2 },
    message: "Voz calibrada.",
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
  processor = { onaudioprocess: null }
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
      createScriptProcessor = () => Object.assign(processor, { connect: vi.fn(), disconnect: vi.fn() })
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

function feedAudio(samples: number) {
  const input = new Float32Array(samples).fill(0.1)
  processor.onaudioprocess?.({
    inputBuffer: { getChannelData: () => input },
    outputBuffer: { getChannelData: () => new Float32Array(samples) },
  })
}

it("offers the voice calibration only after the gaze zone is calibrated", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  stubCapture()
  show()
  await activate()
  expect(screen.getByTestId("gaze-calibration")).toBeInTheDocument()
  expect(screen.queryByTestId("voice-calibration")).not.toBeInTheDocument()
  cleanup()

  useTrial({ ...baseTrial, gaze_zone: zone })
  show()
  await activate()
  expect(await screen.findByTestId("voice-calibration")).toBeInTheDocument()
})

it("records the silence and the phrase, posts audio and mouth telemetry and marks the voice as calibrated", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  stubCapture()
  useTrial({ ...baseTrial, gaze_zone: zone })
  show()
  await activate()
  expect(screen.getByTestId("voice-status")).toHaveTextContent("Huella de voz: pendiente")
  fireEvent.click(await screen.findByRole("button", { name: "Empezar calibración de voz" }))
  await act(async () => {
    await vi.advanceTimersByTimeAsync(3000)
  })
  act(() => feedAudio(144_000)) // 9 s of microphone audio at 16 kHz reaches the recording
  await act(async () => {
    await vi.advanceTimersByTimeAsync(6000)
  })
  await waitFor(() => expect(api.calibrateVoice).toHaveBeenCalledTimes(1))
  const [trialId, , request] = vi.mocked(api.calibrateVoice).mock.calls[0]
  expect(trialId).toBe(baseTrial.id)
  expect(request.audio_samples.length).toBe(144_000)
  expect(request.ambient_ms).toBe(2000)
  expect(request.mouth_samples).toEqual([{ t_ms: 120, mouth_open: 0.2 }])
  // Contract B: 20-130 server frames, offsets from the recording start, inside the audio, at least 40 ms apart.
  expect(request.frames.length).toBeGreaterThanOrEqual(20)
  expect(request.frames.length).toBeLessThanOrEqual(130)
  expect(request.frames.every((frame) => frame.image.startsWith("data:image/jpeg;base64,"))).toBe(true)
  expect(request.frames.every((frame, index) => index === 0 || frame.t_ms - request.frames[index - 1].t_ms >= 40)).toBe(true)
  expect(request.frames.at(-1)!.t_ms).toBeLessThanOrEqual(9000)
  expect(tracker.takeMouthSamples).toHaveBeenCalledWith(expect.any(Number), 9000)
  expect(await screen.findByText("Voz calibrada.")).toBeInTheDocument()
  expect(screen.getByTestId("voice-status")).toHaveTextContent("Huella de voz: calibrada")
})

it("shows the server message verbatim when the voice calibration is rejected", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  stubCapture()
  useTrial({ ...baseTrial, gaze_zone: zone })
  const message = "Se detectó más de una voz durante la calibración. Tiene que hablar solo vos, sin otras personas ni audio reproducido, y repetí la calibración."
  vi.mocked(api.calibrateVoice).mockRejectedValue(new Error(message))
  show()
  await activate()
  fireEvent.click(await screen.findByRole("button", { name: "Empezar calibración de voz" }))
  act(() => feedAudio(144_000))
  await act(async () => {
    await vi.advanceTimersByTimeAsync(9500)
  })
  expect(await screen.findByText(message)).toBeInTheDocument()
  expect(screen.getByTestId("voice-status")).toHaveTextContent("Huella de voz: pendiente")
})

it("labels the new incident kinds in Spanish in the ledger", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  stubCapture()
  const kinds: api.IncidentKind[] = ["VOICE_MISMATCH", "VOICE_UNVERIFIED", "LIP_SYNC_MISMATCH", "BACKGROUND_AUDIO"]
  vi.mocked(api.readBrowserLedger).mockResolvedValue({
    statuscode: 200,
    message: "ok",
    count: kinds.length,
    data: kinds.map((kind, index) => ({
      event_id: `00000000-0000-4000-8000-00000000000${index}`,
      kind,
      observed_at: new Date().toISOString(),
      duration_ms: 0,
      sequence: index + 1,
      received_at: new Date().toISOString(),
    })),
  })
  show()
  await activate()
  expect(await screen.findByText(/La voz no coincide con la persona/)).toBeInTheDocument()
  expect(screen.getByText(/Voz sin verificar/)).toBeInTheDocument()
  expect(screen.getByText(/La voz no coincide con los labios/)).toBeInTheDocument()
  expect(screen.getByText(/Audio de fondo o reproducción/)).toBeInTheDocument()
})

it("reports the voice verdicts in the acoustic activity card", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  stubCapture()
  useTrial({ ...baseTrial, gaze_zone: zone, voice_enrolled: true })
  vi.mocked(api.sendAVWindow).mockResolvedValue({
    ...windowResult,
    speech_detected: true,
    mouth_moving: true,
    mouth_sync: false,
    voice_match: false,
    lip_sync: "unsynced",
  })
  show()
  await activate()
  await runWindow()
  expect(await screen.findByText("Voz distinta a la calibrada")).toBeInTheDocument()
  expect(screen.getByText(/la voz no coincide con la huella de voz calibrada/i)).toBeInTheDocument()
})

it("says the voice is unverified when speech arrives without an enrolled voiceprint", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  stubCapture()
  vi.mocked(api.sendAVWindow).mockResolvedValue({
    ...windowResult,
    speech_detected: true,
    mouth_moving: true,
    mouth_sync: true,
    voice_match: null,
    lip_sync: "synced",
  })
  show()
  await activate()
  await runWindow()
  expect(await screen.findByText("Voz sin verificar")).toBeInTheDocument()
})

it("says the lips do not match the voice when the correlation fails", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  stubCapture()
  useTrial({ ...baseTrial, voice_enrolled: true })
  vi.mocked(api.sendAVWindow).mockResolvedValue({
    ...windowResult,
    speech_detected: true,
    mouth_sync: false,
    voice_match: true,
    lip_sync: "unsynced",
  })
  show()
  await activate()
  await runWindow()
  expect(await screen.findByText("Voz sin labios coincidentes")).toBeInTheDocument()
})

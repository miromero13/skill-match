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

function stubCapture(samplesPerCallback: number) {
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
  vi.spyOn(HTMLCanvasElement.prototype, "toDataURL").mockReturnValue("data:image/jpeg;base64,AAAA")
  const processor: { onaudioprocess: ((event: unknown) => void) | null } = { onaudioprocess: null }
  class FakeAudioContext {
    sampleRate = 16000
    state = "running"
    destination = {}
    resume = () => Promise.resolve()
    close = () => Promise.resolve()
    createMediaStreamSource = () => ({ connect: vi.fn() })
    createAnalyser = () => ({ fftSize: 1024, connect: vi.fn(), getFloatTimeDomainData: vi.fn() })
    createScriptProcessor = () => Object.assign(processor, { connect: vi.fn(), disconnect: vi.fn() })
  }
  vi.stubGlobal("AudioContext", FakeAudioContext)
  const feed = () =>
    processor.onaudioprocess?.({
      outputBuffer: { getChannelData: () => new Float32Array(samplesPerCallback) },
      inputBuffer: { getChannelData: () => new Float32Array(samplesPerCallback) },
    })
  return { feed }
}

async function runWindows(count: number, feed?: () => void) {
  for (let i = 0; i < count * 6; i++) {
    feed?.()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(400)
    })
  }
}

it("sends duration_ms equal to the audio actually captured", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  const { feed } = stubCapture(2048)
  show()
  await activate()
  await runWindows(1, feed)
  expect(api.sendAVWindow).toHaveBeenCalled()
  const payload = vi.mocked(api.sendAVWindow).mock.calls[0][1]
  expect(payload.audio_samples?.length).toBeGreaterThan(0)
  expect(payload.duration_ms).toBe(api.avWindowDurationMs(payload.audio_samples?.length ?? 0))
  expect(payload.duration_ms).not.toBe(2400)
  expect(payload.frames.length).toBeGreaterThan(0)
})

it("surfaces failed audiovisual windows and queues one STREAM_ERROR after repeated failures", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  const { feed } = stubCapture(2048)
  vi.mocked(api.sendAVWindow).mockRejectedValue(new Error("Servidor sin respuesta"))
  show()
  await activate()
  await runWindows(1, feed)
  expect(screen.getByTestId("av-status")).toHaveTextContent("Servidor sin respuesta")
  const sentKinds = () =>
    vi.mocked(api.sendBrowserIncidents).mock.calls.flatMap(call => call[2].map(row => row.kind))
  expect(sentKinds()).not.toContain("STREAM_ERROR")
  await runWindows(1, feed)
  await waitFor(() => expect(sentKinds().filter(kind => kind === "STREAM_ERROR")).toHaveLength(1))
  await runWindows(1, feed)
  expect(sentKinds().filter(kind => kind === "STREAM_ERROR")).toHaveLength(1)
  vi.mocked(api.sendAVWindow).mockResolvedValue({
    window_id: "ok",
    face_count: 1,
    head_orientation: "CENTER",
    identity_match: null,
    speech_detected: false,
    noise_level: 0,
    anomalies: [],
    incidents_created: [],
  })
  await runWindows(1, feed)
  await waitFor(() => expect(screen.queryByTestId("av-status")).not.toBeInTheDocument())
})

it("labels the new evidence incidents in Spanish", async () => {
  vi.mocked(api.readBrowserLedger).mockResolvedValue({
    statuscode: 200,
    message: "Bitácora de prueba recuperada.",
    data: (["VIDEO_MISSING", "AUDIO_MISSING", "WINDOW_GAP", "MODEL_UNAVAILABLE"] as const).map((kind, index) => ({
      event_id: `00000000-0000-4000-8000-00000000000${index}`,
      kind,
      observed_at: new Date().toISOString(),
      duration_ms: 0,
      sequence: index + 1,
      received_at: new Date().toISOString(),
    })),
    count: 4,
  })
  localStorage.setItem("sm43:last:member", trial.id)
  vi.mocked(api.readBrowserTrial).mockResolvedValue(trial)
  show()
  for (const label of ["Sin video", "Sin audio", "Supervisión interrumpida", "Modelo de IA no disponible"])
    expect(await screen.findByText(new RegExp(label))).toBeInTheDocument()
})

it("labels the occlusion and camera incidents in Spanish", async () => {
  vi.mocked(api.readBrowserLedger).mockResolvedValue({
    statuscode: 200,
    message: "Bitácora de prueba recuperada.",
    data: (["FACE_OCCLUDED", "MOUTH_OCCLUDED", "CAMERA_BLOCKED"] as const).map((kind, index) => ({
      event_id: `00000000-0000-4000-8000-00000000001${index}`,
      kind,
      observed_at: new Date().toISOString(),
      duration_ms: 1200,
      sequence: index + 1,
      received_at: new Date().toISOString(),
    })),
    count: 3,
  })
  localStorage.setItem("sm43:last:member", trial.id)
  vi.mocked(api.readBrowserTrial).mockResolvedValue(trial)
  show()
  for (const label of ["Rostro cubierto", "Boca cubierta", "Cámara tapada o congelada"])
    expect(await screen.findByText(new RegExp(label))).toBeInTheDocument()
})

it.each([
  [{ occlusion: { face: true, mouth: false } }, "Rostro cubierto"],
  [{ occlusion: { face: false, mouth: true } }, "Boca cubierta"],
  [{ camera_blocked: true }, "Cámara tapada o congelada"],
])("shows %j in the facial presence card and stops verifying the profile", async (flags, label) => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  const { feed } = stubCapture(2048)
  vi.mocked(api.sendAVWindow).mockResolvedValue({
    window_id: "covered",
    face_count: 1,
    head_orientation: "CENTER",
    identity_match: null,
    speech_detected: false,
    noise_level: 0,
    anomalies: [],
    incidents_created: [],
    ...flags,
  })
  show()
  await activate()
  await runWindows(1, feed)
  await waitFor(() => expect(screen.getAllByText(label).length).toBeGreaterThan(0))
  expect(screen.getByText("No verificable")).toBeInTheDocument()
})

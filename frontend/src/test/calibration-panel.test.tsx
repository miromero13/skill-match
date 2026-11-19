import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import { useState } from "react"
import { CalibrationPanel } from "@/components/evaluations/calibration-panel"
import { CHECK_LABELS } from "@/components/evaluations/calibration-checks"
import { requestCalibrationChallenge, verifyEvaluationCalibration, type CalibrationState } from "@/services/evaluation-service"
import { createMicrophoneRecorder } from "@/services/av-capture"
import { ApiError } from "@/types/api"
import { startFaceTracker } from "@/services/gaze-tracking"

vi.mock("@/services/evaluation-service", () => ({
  requestCalibrationChallenge: vi.fn(), verifyEvaluationCalibration: vi.fn(),
}))
vi.mock("@/services/av-capture", async (original) => ({ ...(await original<typeof import("@/services/av-capture")>()), createMicrophoneRecorder: vi.fn() }))
vi.mock("@/services/gaze-tracking", async (original) => ({ ...(await original<typeof import("@/services/gaze-tracking")>()), startFaceTracker: vi.fn() }))

const stopTrack = vi.fn()
const closeRecorder = vi.fn().mockResolvedValue(undefined)
const stopTracker = vi.fn()
const getUserMedia = vi.fn()
const media = {
  getTracks: () => [{ stop: stopTrack }],
  getVideoTracks: () => [{ label: "Physical webcam", readyState: "live", getSettings: () => ({ deviceId: "camera-1" }) }],
  getAudioTracks: () => [{ readyState: "live" }],
}
let mouth: { t_ms: number; mouth_open: number }[]
const allChecks = (value = true): Record<string, boolean> => Object.fromEntries(Object.keys(CHECK_LABELS).map((key) => [key, value]))
const state = (overrides: Partial<CalibrationState> = {}): CalibrationState => ({
  evaluation_id: "evaluation-1", ready: true, status: "READY_FOR_THEORY", started_at: null, checks: allChecks(), ...overrides,
})

beforeEach(() => {
  vi.clearAllMocks()
  mouth = Array.from({ length: 150 }, (_, index) => ({ t_ms: index * 70, mouth_open: 0.2 }))
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia, enumerateDevices: vi.fn().mockResolvedValue([]) } })
  getUserMedia.mockResolvedValue(media)
  Object.defineProperty(HTMLVideoElement.prototype, "videoWidth", { value: 640, configurable: true })
  Object.defineProperty(HTMLVideoElement.prototype, "videoHeight", { value: 480, configurable: true })
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({ drawImage: vi.fn() } as never)
  vi.spyOn(HTMLCanvasElement.prototype, "toDataURL").mockReturnValue("data:image/jpeg;base64,FRAME")
  vi.mocked(createMicrophoneRecorder).mockImplementation(async () => {
    let startedAt = 0
    return {
      start: () => { startedAt = Date.now() },
      stop: () => ({ samples: new Array<number>(11 * 16_000).fill(0.02), startedAt }),
      close: closeRecorder,
    }
  })
  vi.mocked(startFaceTracker).mockImplementation(async () => ({
    setZone: vi.fn(), takeSamples: vi.fn(() => []), takeMouthSamples: vi.fn(() => mouth), stop: stopTracker,
  }))
  vi.mocked(requestCalibrationChallenge).mockResolvedValue({ id: "challenge-1", action: "TURN_LEFT", expires_at: "2026-11-18T00:00:05Z" })
  vi.mocked(verifyEvaluationCalibration).mockResolvedValue(state())
})
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks() })

const tick = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms) })
const press = (name: string | RegExp) => act(async () => { fireEvent.click(screen.getByRole("button", { name })); await vi.advanceTimersByTimeAsync(0) })

/** Mounts the panel, grants devices and shows the first frame of the preview. */
async function prepared() {
  vi.useFakeTimers()
  const view = render(<CalibrationPanel evaluationId="evaluation-1" />)
  await press("Preparar cámara y micrófono")
  fireEvent.loadedData(view.container.querySelector("video")!)
  return view
}

describe("devices and fail-closed preparation", () => {
  it("never activates camera, microphone or challenge automatically", () => {
    render(<CalibrationPanel evaluationId="evaluation-1" />)
    expect(getUserMedia).not.toHaveBeenCalled()
    expect(requestCalibrationChallenge).not.toHaveBeenCalled()
    expect(screen.getByRole("button", { name: "Comenzar primera prueba" })).toBeDisabled()
  })

  it("reports denied permissions without issuing a challenge", async () => {
    getUserMedia.mockRejectedValue(new DOMException("Denied", "NotAllowedError"))
    render(<CalibrationPanel evaluationId="evaluation-1" />)
    fireEvent.click(screen.getByRole("button", { name: "Preparar cámara y micrófono" }))
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo acceder a la cámara o al micrófono")
    expect(requestCalibrationChallenge).not.toHaveBeenCalled()
  })

  it("fails closed and releases everything when the face tracker cannot start", async () => {
    vi.mocked(startFaceTracker).mockRejectedValue(new Error("no model"))
    render(<CalibrationPanel evaluationId="evaluation-1" />)
    fireEvent.click(screen.getByRole("button", { name: "Preparar cámara y micrófono" }))
    expect(await screen.findByRole("alert")).toHaveTextContent(/análisis del rostro/)
    expect(stopTrack).toHaveBeenCalled()
    expect(closeRecorder).toHaveBeenCalled()
    expect(screen.queryByTestId("gaze-calibration")).not.toBeInTheDocument()
  })

  it("rejects a camera below 320x240 before any step starts", async () => {
    Object.defineProperty(HTMLVideoElement.prototype, "videoWidth", { value: 160, configurable: true })
    const view = render(<CalibrationPanel evaluationId="evaluation-1" />)
    fireEvent.click(screen.getByRole("button", { name: "Preparar cámara y micrófono" }))
    await screen.findByLabelText("Vista previa de cámara")
    fireEvent.loadedData(view.container.querySelector("video")!)
    expect(await screen.findByRole("alert")).toHaveTextContent(/320×240/)
  })

  it("releases camera, microphone, tracker and recorder when returning to the integrity step", async () => {
    function Review() {
      const [calibrating, setCalibrating] = useState(true)
      return calibrating ? <CalibrationPanel evaluationId="evaluation-1" onBack={() => setCalibrating(false)} /> : <p>Normas de integridad</p>
    }
    render(<Review />)
    fireEvent.click(screen.getByRole("button", { name: "Preparar cámara y micrófono" }))
    await screen.findByTestId("gaze-calibration")
    fireEvent.click(screen.getByRole("button", { name: "Volver a Normas" }))
    expect(screen.getByText("Normas de integridad")).toBeInTheDocument()
    expect(stopTrack).toHaveBeenCalled()
    expect(closeRecorder).toHaveBeenCalled()
    expect(stopTracker).toHaveBeenCalled()
    expect(verifyEvaluationCalibration).not.toHaveBeenCalled()
  })

  it("releases granted devices when it unmounts mid-preparation and on unmount while a step is running", async () => {
    const view = await prepared()
    await press("Empezar calibración")
    await tick(1500)
    view.unmount()
    expect(stopTrack).toHaveBeenCalled()
    expect(closeRecorder).toHaveBeenCalledOnce()
    expect(stopTracker).toHaveBeenCalledOnce()
    await tick(30_000)
    expect(requestCalibrationChallenge).not.toHaveBeenCalled()
    expect(vi.getTimerCount()).toBe(0)
  })
})

async function runGuidedFlow() {
  await press("Empezar calibración")
  await tick(9_500) // centre + four corners
  expect(requestCalibrationChallenge).not.toHaveBeenCalled()
  await press("Empezar giro de cabeza")
  await tick(11_500)
  await tick(11_500) // the silence and phrase start by themselves: the challenge lives only 45 s
}

describe("guided flow on the engine contract", () => {
  it("runs gaze, head turn, silence and phrase in order and sends one contract A request", async () => {
    await prepared()
    expect(screen.getByTestId("gaze-calibration")).toBeInTheDocument()
    expect(screen.queryByTestId("head-turn")).not.toBeInTheDocument()
    await press("Empezar calibración")
    await tick(9_500)
    expect(screen.getByTestId("head-turn")).toBeInTheDocument()
    expect(requestCalibrationChallenge).not.toHaveBeenCalled() // the challenge is only issued for the head turn
    await press("Empezar giro de cabeza")
    expect(requestCalibrationChallenge).toHaveBeenCalledWith("evaluation-1")
    await tick(11_500)
    expect(screen.getByTestId("voice-calibration")).toBeInTheDocument()
    expect(verifyEvaluationCalibration).not.toHaveBeenCalled()
    await tick(11_500) // no idle wait: the voice step starts on its own
    expect(verifyEvaluationCalibration).toHaveBeenCalledTimes(1)
    const [id, evidence] = vi.mocked(verifyEvaluationCalibration).mock.calls[0]
    expect(id).toBe("evaluation-1")
    expect(Object.keys(evidence).sort()).toEqual([
      "ambient_audio_samples", "audio_samples", "camera_label", "challenge_id", "frames", "gaze_points", "mouth_samples", "spoken_frames",
    ])
    expect(evidence.challenge_id).toBe("challenge-1")
    expect(evidence.frames).toHaveLength(12)
    expect(evidence.gaze_points.map((point) => point.target)).toEqual(["CENTER", "TOP_LEFT", "TOP_RIGHT", "BOTTOM_LEFT", "BOTTOM_RIGHT"])
    expect(evidence.gaze_points.every((point) => point.frames.length >= 1 && point.frames.length <= 6)).toBe(true)
    expect(evidence.ambient_audio_samples).toHaveLength(48_000)
    expect(evidence.audio_samples.length).toBeGreaterThanOrEqual(112_000)
    expect(evidence.audio_samples.length).toBeLessThanOrEqual(160_000)
    expect(evidence.spoken_frames.length).toBeGreaterThanOrEqual(20)
    expect(evidence.spoken_frames.length).toBeLessThanOrEqual(100)
    expect(evidence.mouth_samples.length).toBeGreaterThanOrEqual(8)
    expect(evidence.mouth_samples.every((sample, index) => index === 0 || sample.t_ms - evidence.mouth_samples[index - 1].t_ms >= 30)).toBe(true)
    expect(evidence.camera_label).toBe("Physical webcam")
  })

  it.each([["TURN_LEFT", "derecha"], ["TURN_RIGHT", "izquierda"]] as const)("guides the %s turn in the mirrored preview", async (action, side) => {
    vi.mocked(requestCalibrationChallenge).mockResolvedValue({ id: "challenge-1", action, expires_at: "2026-11-18T00:00:05Z" })
    const view = await prepared()
    expect(view.container.querySelector("video")).toHaveClass("-scale-x-100")
    await press("Empezar calibración")
    await tick(9_500)
    await press("Empezar giro de cabeza")
    await tick(4_500)
    expect(screen.getByTestId("head-turn-status")).toHaveTextContent(`Girá hacia tu ${side}.`)
  })

  it("shows success with Spanish labels for all 21 checks, ends the capture and never starts the exam", async () => {
    await prepared()
    await runGuidedFlow()
    expect(screen.getByText("Comprobación superada")).toBeInTheDocument()
    for (const label of Object.values(CHECK_LABELS)) expect(screen.getByText(label)).toBeInTheDocument()
    for (const key of Object.keys(CHECK_LABELS)) expect(screen.queryByText(key)).not.toBeInTheDocument()
    expect(screen.getByText(/El examen no comenzó y tu intento no se descontó/)).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Continuar al examen oral" })).toHaveAttribute("href", "/evaluation/evaluation-1/theory")
    expect(stopTrack).toHaveBeenCalled()
    expect(closeRecorder).toHaveBeenCalled()
    expect(stopTracker).toHaveBeenCalled()
  })
})

describe("failures", () => {
  it("lists the failed checks with their Spanish labels and an unknown key as it came", async () => {
    vi.mocked(verifyEvaluationCalibration).mockResolvedValue(state({
      ready: false, status: "PENDING_CALIBRATION", checks: { ...allChecks(), gaze_zone: false, single_speaker: false, future_check: false },
    }))
    await prepared()
    await runGuidedFlow()
    const failed = screen.getAllByText("Revisar").map((badge) => badge.parentElement!.textContent)
    expect(failed).toHaveLength(3)
    expect(failed.join("|")).toContain(CHECK_LABELS.gaze_zone)
    expect(failed.join("|")).toContain(CHECK_LABELS.single_speaker)
    expect(failed.join("|")).toContain("future_check")
    expect(screen.queryByText("Comprobación superada")).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Repetir calibración" })).toBeEnabled()
    expect(screen.getByRole("button", { name: "Comenzar primera prueba" })).toBeDisabled()
  })

  it("does not trust ready=true when a returned check failed", async () => {
    vi.mocked(verifyEvaluationCalibration).mockResolvedValue(state({ checks: { ...allChecks(), identity: false } }))
    await prepared()
    await runGuidedFlow()
    expect(screen.queryByText("Comprobación superada")).not.toBeInTheDocument()
    expect(screen.getByText("Revisar")).toBeInTheDocument()
  })

  it("shows the backend message verbatim and lets the member repeat everything", async () => {
    const message = "Tu voz no coincide con el movimiento de tus labios. Mirá la cámara, leé la frase en voz alta y repetí la comprobación."
    vi.mocked(verifyEvaluationCalibration).mockRejectedValueOnce(new Error(message))
    await prepared()
    await runGuidedFlow()
    expect(screen.getByRole("alert")).toHaveTextContent(message)
    expect(screen.getByRole("button", { name: "Comenzar primera prueba" })).toBeDisabled()
    await press("Repetir calibración")
    expect(screen.getByTestId("gaze-calibration")).toBeInTheDocument()
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })

  it("does not send anything when the browser captured fewer than 8 mouth readings", async () => {
    mouth = mouth.slice(0, 3)
    await prepared()
    await runGuidedFlow()
    expect(screen.getByRole("alert")).toHaveTextContent(/boca/)
    expect(verifyEvaluationCalibration).not.toHaveBeenCalled()
  })
})

describe("shared integrity units (S9)", () => {
  it("uses the same gaze and voice steps as the trial page", async () => {
    const panel = (await import("@/components/evaluations/calibration-panel.tsx?raw")).default
    const trial = (await import("@/components/integrity/calibration-gate.tsx?raw")).default // the trial page's gate
    for (const source of [panel, trial]) {
      expect(source).toContain('from "@/components/integrity/gaze-calibration-step"')
      expect(source).toContain('from "@/components/integrity/voice-calibration-step"')
    }
    expect(panel).toContain('from "@/services/av-capture"')
  })
})

describe("challenge expiry (the server issues it for 45 s)", () => {
  async function throughGaze() {
    await prepared()
    await press("Empezar calibración")
    await tick(9_500)
  }

  it("starts the silence and phrase by itself as soon as the head turn is captured", async () => {
    await throughGaze()
    await press("Empezar giro de cabeza")
    await tick(11_500)
    expect(screen.getByTestId("voice-calibration-status")).toHaveTextContent(/silencio/i)
    expect(screen.queryByRole("button", { name: "Empezar calibración de voz" })).not.toBeInTheDocument()
  })

  it("restarts from a new challenge, keeping the gaze, when too little time is left for the voice step", async () => {
    await throughGaze()
    await press("Empezar giro de cabeza")
    await tick(4_000)
    vi.setSystemTime(Date.now() + 35_000) // the capture stalled: ~35 s of the 45 s are gone
    await tick(7_500)
    expect(screen.getByRole("alert")).toHaveTextContent(/El reto del giro de cabeza venció/)
    expect(screen.getByTestId("head-turn")).toBeInTheDocument()
    expect(screen.queryByTestId("gaze-calibration")).not.toBeInTheDocument() // the completed gaze step is kept
    expect(screen.queryByTestId("voice-calibration")).not.toBeInTheDocument()
    expect(verifyEvaluationCalibration).not.toHaveBeenCalled()

    vi.mocked(requestCalibrationChallenge).mockResolvedValue({ id: "challenge-2", action: "TURN_RIGHT", expires_at: "2026-11-18T00:00:05Z" })
    await press("Empezar giro de cabeza")
    expect(requestCalibrationChallenge).toHaveBeenCalledTimes(2)
    await tick(11_500)
    await tick(11_500)
    expect(verifyEvaluationCalibration).toHaveBeenCalledTimes(1)
    const evidence = vi.mocked(verifyEvaluationCalibration).mock.calls[0][1]
    expect(evidence.challenge_id).toBe("challenge-2")
    expect(evidence.gaze_points).toHaveLength(5)
  })

  it("shows the server's 410 message verbatim and restarts from the challenge without losing the gaze", async () => {
    const expired = "El reto venció. Solicitá uno nuevo; tu intento no se descontó."
    vi.mocked(verifyEvaluationCalibration).mockRejectedValueOnce(new ApiError(expired, 410))
    await throughGaze()
    await press("Empezar giro de cabeza")
    await tick(11_500)
    await tick(11_500)
    expect(screen.getByRole("alert")).toHaveTextContent(expired)
    expect(screen.getByTestId("head-turn")).toBeInTheDocument()
    expect(screen.queryByTestId("gaze-calibration")).not.toBeInTheDocument()
    expect(screen.queryByTestId("voice-calibration")).not.toBeInTheDocument()
  })
})

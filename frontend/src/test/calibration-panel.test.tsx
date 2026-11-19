import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useState } from "react"
import { CalibrationPanel } from "@/components/evaluations/calibration-panel"
import { requestCalibrationChallenge, verifyEvaluationCalibration } from "@/services/evaluation-service"
import { captureCalibrationEvidence, createMicrophoneMonitor } from "@/services/calibration-capture"

vi.mock("@/services/evaluation-service", () => ({
  requestCalibrationChallenge: vi.fn(), verifyEvaluationCalibration: vi.fn(),
}))
vi.mock("@/services/calibration-capture", () => ({
  captureCalibrationEvidence: vi.fn(), createMicrophoneMonitor: vi.fn(),
}))

const stop = vi.fn()
const close = vi.fn().mockResolvedValue(undefined)
const getUserMedia = vi.fn()
const media = {
  getTracks: () => [{ stop }],
  getVideoTracks: () => [{ label: "Physical webcam", readyState: "live", getSettings: () => ({ deviceId: "camera-1" }) }],
  getAudioTracks: () => [{ readyState: "live" }],
}

beforeEach(() => {
  vi.clearAllMocks()
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: {
    getUserMedia, enumerateDevices: vi.fn().mockResolvedValue([]),
  } })
  getUserMedia.mockResolvedValue(media)
  vi.mocked(createMicrophoneMonitor).mockResolvedValue({ samples: () => [0.1], close })
  vi.mocked(captureCalibrationEvidence).mockResolvedValue({ frames: ["a", "b", "c"], audio_samples: [0.1], ambient_audio_samples: [0], spoken_frames: [{ time_ms: 100, image: "spoken-frame" }] })
  vi.mocked(requestCalibrationChallenge).mockResolvedValue({ id: "challenge-1", action: "TURN_LEFT", expires_at: "2026-11-18T00:00:05Z" })
  vi.mocked(verifyEvaluationCalibration).mockResolvedValue({
    evaluation_id: "evaluation-1", ready: true, status: "READY_FOR_THEORY", started_at: null,
    checks: { lighting: true, framing: true, single_face: true, microphone: true, identity: true, liveness: true, passive_screen_check: true,
      background_quiet: true, single_speaker: true, no_overlap: true, mouth_audio_sync: true, speech_pause: true },
  })
})
afterEach(cleanup)

describe("shared calibration panel", () => {
  it("never activates camera or microphone automatically", () => {
    render(<CalibrationPanel evaluationId="evaluation-1" />)
    expect(getUserMedia).not.toHaveBeenCalled()
    expect(requestCalibrationChallenge).not.toHaveBeenCalled()
    expect(screen.getByRole("button", { name: "Comenzar primera prueba" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "Comprobar ambiente e identidad" })).toBeDisabled()
  })

  it("reports denied permissions without issuing a challenge", async () => {
    getUserMedia.mockRejectedValue(new DOMException("Denied", "NotAllowedError"))
    render(<CalibrationPanel evaluationId="evaluation-1" />)
    await userEvent.click(screen.getByRole("button", { name: "Preparar cámara y micrófono" }))
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo acceder a la cámara o al micrófono")
    expect(requestCalibrationChallenge).not.toHaveBeenCalled()
  })

  it("captures after permission, submits the challenge, releases devices and never starts the exam", async () => {
    const user = userEvent.setup()
    const view = render(<CalibrationPanel evaluationId="evaluation-1" />)
    await user.click(screen.getByRole("button", { name: "Preparar cámara y micrófono" }))
    const video = view.container.querySelector("video")!
    fireEvent.loadedData(video)
    await user.click(screen.getByRole("button", { name: "Comprobar ambiente e identidad" }))
    expect(await screen.findByText("Comprobación superada")).toBeInTheDocument()
    expect(verifyEvaluationCalibration).toHaveBeenCalledWith("evaluation-1", {
      challenge_id: "challenge-1", camera_label: "Physical webcam",
      frames: ["a", "b", "c"], audio_samples: [0.1], ambient_audio_samples: [0], spoken_frames: [{ time_ms: 100, image: "spoken-frame" }],
    })
    expect(screen.getByText(/El examen no comenzó y tu intento no se descontó/)).toBeInTheDocument()
    await waitFor(() => expect(stop).toHaveBeenCalled())
    expect(close).toHaveBeenCalled()
  })

  it.each([
    ["TURN_LEFT", "derecha"],
    ["TURN_RIGHT", "izquierda"],
  ] as const)("guides each capture phase for %s in the mirrored preview", async (action, side) => {
    vi.mocked(requestCalibrationChallenge).mockResolvedValue({ id: "challenge-1", action, expires_at: "2026-11-18T00:00:05Z" })
    let guide: ((phase: "CENTER" | "TURN" | "RETURN" | "AMBIENT" | "SPEAK" | "PAUSE") => void) | undefined
    let finish: ((evidence: { frames: string[]; audio_samples: number[]; ambient_audio_samples: number[]; spoken_frames: { time_ms: number; image: string }[] }) => void) | undefined
    vi.mocked(captureCalibrationEvidence).mockImplementation((_video, _microphone, _signal, onPhase) => {
      guide = onPhase
      onPhase?.("CENTER")
      return new Promise(resolve => { finish = resolve })
    })
    const user = userEvent.setup()
    const view = render(<CalibrationPanel evaluationId="evaluation-1" />)
    expect(screen.getByText(/La dirección aparecerá al comenzar/)).toBeInTheDocument()
    expect(view.container.querySelector("video")).toHaveClass("-scale-x-100")
    await user.click(screen.getByRole("button", { name: "Preparar cámara y micrófono" }))
    fireEvent.loadedData(view.container.querySelector("video")!)
    await user.click(screen.getByRole("button", { name: "Comprobar ambiente e identidad" }))
    expect(await screen.findByRole("heading", { name: "Mirá al centro y quedate quieto." })).toBeInTheDocument()
    expect(verifyEvaluationCalibration).not.toHaveBeenCalled()
    act(() => guide?.("TURN"))
    expect(screen.getByRole("heading", { name: `Girá hacia tu ${side}.` })).toBeInTheDocument()
    expect(screen.getByText("Paso 2 de 3 · Movimiento")).toBeInTheDocument()
    act(() => guide?.("RETURN"))
    expect(screen.getByRole("heading", { name: "Volvé al centro y quedate quieto." })).toBeInTheDocument()
    expect(screen.getByText("Paso 3 de 3 · Movimiento")).toBeInTheDocument()
    act(() => guide?.("AMBIENT"))
    expect(screen.getByRole("heading", { name: "Guardá silencio durante 3 segundos." })).toBeInTheDocument()
    expect(verifyEvaluationCalibration).not.toHaveBeenCalled()
    act(() => guide?.("SPEAK"))
    expect(screen.getByRole("heading", { name: "Decí: «Estoy listo para comenzar»." })).toBeInTheDocument()
    expect(verifyEvaluationCalibration).not.toHaveBeenCalled()
    act(() => guide?.("PAUSE"))
    expect(screen.getByRole("heading", { name: "Ahora guardá silencio y mantené la boca quieta." })).toBeInTheDocument()
    await act(async () => finish?.({ frames: ["a", "b", "c"], audio_samples: [0.1], ambient_audio_samples: [0], spoken_frames: [{ time_ms: 100, image: "spoken-frame" }] }))
    expect(await screen.findByText("Comprobación superada")).toBeInTheDocument()
    expect(verifyEvaluationCalibration).toHaveBeenCalledTimes(1)
    expect(screen.getByRole("link", { name: "Continuar al examen oral" })).toHaveAttribute("href", "/evaluation/evaluation-1/theory")
  })

  it("keeps the requested direction visible after a rejected movement", async () => {
    const message = "No se completó el movimiento solicitado. Mirá al centro, girá hacia el lado indicado y volvé al centro."
    vi.mocked(verifyEvaluationCalibration).mockRejectedValueOnce(new Error(message))
    const user = userEvent.setup()
    const view = render(<CalibrationPanel evaluationId="evaluation-1" />)
    await user.click(screen.getByRole("button", { name: "Preparar cámara y micrófono" }))
    fireEvent.loadedData(view.container.querySelector("video")!)
    await user.click(screen.getByRole("button", { name: "Comprobar ambiente e identidad" }))
    expect(await screen.findByRole("alert")).toHaveTextContent(message)
    expect(screen.getByText(/El movimiento solicitado fue hacia tu derecha/)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Comprobar ambiente e identidad" })).toBeEnabled()
    expect(screen.getByRole("button", { name: "Comenzar primera prueba" })).toBeDisabled()
  })

  it("releases devices when returning to the integrity step", async () => {
    function Review() {
      const [calibrating, setCalibrating] = useState(true)
      return calibrating
        ? <CalibrationPanel evaluationId="evaluation-1" onBack={() => setCalibrating(false)} />
        : <p>Normas de integridad</p>
    }
    render(<Review />)
    await userEvent.click(screen.getByRole("button", { name: "Preparar cámara y micrófono" }))
    await userEvent.click(screen.getByRole("button", { name: "Volver a Normas" }))
    expect(screen.getByText("Normas de integridad")).toBeInTheDocument()
    expect(stop).toHaveBeenCalled()
    expect(close).toHaveBeenCalled()
    expect(verifyEvaluationCalibration).not.toHaveBeenCalled()
  })

  it("releases granted devices when leaving the panel", async () => {
    const view = render(<CalibrationPanel evaluationId="evaluation-1" />)
    await userEvent.click(screen.getByRole("button", { name: "Preparar cámara y micrófono" }))
    view.unmount()
    expect(stop).toHaveBeenCalled()
    expect(close).toHaveBeenCalled()
    expect(verifyEvaluationCalibration).not.toHaveBeenCalled()
  })
})

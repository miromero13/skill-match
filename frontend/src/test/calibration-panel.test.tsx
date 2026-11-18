import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
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
  vi.mocked(captureCalibrationEvidence).mockResolvedValue({ frames: ["a", "b", "c"], audio_samples: [0.1] })
  vi.mocked(requestCalibrationChallenge).mockResolvedValue({ id: "challenge-1", action: "TURN_LEFT", expires_at: "2026-11-18T00:00:05Z" })
  vi.mocked(verifyEvaluationCalibration).mockResolvedValue({
    evaluation_id: "evaluation-1", ready: true, status: "READY_FOR_THEORY", started_at: null,
    checks: { lighting: true, framing: true, single_face: true, microphone: true, identity: true, liveness: true, passive_screen_check: true },
  })
})
afterEach(cleanup)

describe("shared calibration panel", () => {
  it("never activates camera or microphone automatically", () => {
    render(<CalibrationPanel evaluationId="evaluation-1" />)
    expect(getUserMedia).not.toHaveBeenCalled()
    expect(requestCalibrationChallenge).not.toHaveBeenCalled()
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
      frames: ["a", "b", "c"], audio_samples: [0.1],
    })
    expect(screen.getByText(/El examen no comenzó y tu intento no se descontó/)).toBeInTheDocument()
    await waitFor(() => expect(stop).toHaveBeenCalled())
    expect(close).toHaveBeenCalled()
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

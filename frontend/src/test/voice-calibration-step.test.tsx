import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import {
  VOICE_PHRASE,
  VoiceCalibrationStep,
  type VoiceCalibrationStepProps,
} from "@/components/integrity/voice-calibration-step"

beforeEach(() => vi.useFakeTimers())
afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

/** A nine second recording (2 s silence + 7 s phrase) at 16 kHz whose first sample is the instant start() ran. */
function setup(overrides: Partial<VoiceCalibrationStepProps> = {}, seconds = 9) {
  let startedAt = 0
  const start = vi.fn(() => {
    startedAt = Date.now()
  })
  const stop = vi.fn(() => ({ samples: new Array<number>(seconds * 16_000).fill(0.1), startedAt }))
  const readMouth = vi.fn(() => Array.from({ length: 60 }, (_, index) => ({ t_ms: index * 140, mouth_open: 0.2 })))
  const captureFrame = vi.fn(() => "jpeg-frame")
  const submit = vi.fn<VoiceCalibrationStepProps["submit"]>(async () => ({ message: "Voz calibrada." }))
  const onCalibrated = vi.fn()
  render(
    <VoiceCalibrationStep
      recorder={{ start, stop }}
      readMouth={readMouth}
      captureFrame={captureFrame}
      submit={submit}
      onCalibrated={onCalibrated}
      {...overrides}
    />,
  )
  return { start, stop, readMouth, captureFrame, submit, onCalibrated }
}

const begin = () => fireEvent.click(screen.getByRole("button", { name: "Empezar calibración de voz" }))
const elapse = (ms: number) =>
  act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })

it("starts idle: nothing is recorded and the control phrase is not shown yet", () => {
  const { start, submit, captureFrame } = setup()
  expect(screen.getByText("Pendiente")).toBeInTheDocument()
  expect(screen.queryByTestId("voice-phrase")).not.toBeInTheDocument()
  expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  expect(start).not.toHaveBeenCalled()
  expect(captureFrame).not.toHaveBeenCalled()
  expect(submit).not.toHaveBeenCalled()
})

it("asks for silence first, then shows the control phrase to read aloud", async () => {
  const { start } = setup()
  begin()
  expect(start).toHaveBeenCalledTimes(1)
  expect(screen.getByTestId("voice-calibration-status")).toHaveTextContent(/Quedate en silencio/)
  expect(screen.getByTestId("voice-calibration-status")).toHaveTextContent("2 s")
  expect(screen.queryByTestId("voice-phrase")).not.toBeInTheDocument()
  await elapse(2100)
  expect(screen.getByTestId("voice-phrase")).toHaveTextContent(VOICE_PHRASE)
  expect(screen.getByTestId("voice-calibration-status")).toHaveTextContent(/Leé en voz alta/)
})

it("shows a final silent pause after the phrase when pauseMs is set (the pre-exam calibration)", async () => {
  setup({ ambientMs: 3000, phraseMs: 4000, pauseMs: 4000 }, 11)
  begin()
  await elapse(3100)
  expect(screen.getByTestId("voice-phrase")).toBeInTheDocument()
  await elapse(4000)
  expect(screen.queryByTestId("voice-phrase")).not.toBeInTheDocument()
  expect(screen.getByTestId("voice-calibration-status")).toHaveTextContent(/No hables ni muevas la boca/)
})

it("posts audio, silence length, mouth telemetry and the required 20-130 server frames, message verbatim", async () => {
  const { start, stop, readMouth, submit, onCalibrated } = setup()
  begin()
  await elapse(9_500)
  expect(start).toHaveBeenCalledTimes(1)
  expect(stop).toHaveBeenCalledTimes(1)
  // The mouth readings are asked for the whole recording: from where the audio started, silence included.
  expect(readMouth).toHaveBeenCalledWith(expect.any(Number), 9000)
  expect(submit).toHaveBeenCalledTimes(1)
  const request = submit.mock.calls[0][0]
  expect(request.ambient_ms).toBe(2000)
  expect(request.audio_samples).toHaveLength(144_000)
  expect(request.mouth_samples).toHaveLength(60)
  expect(request.frames.length).toBeGreaterThanOrEqual(20)
  expect(request.frames.length).toBeLessThanOrEqual(130)
  expect(request.frames.every((frame) => frame.image === "jpeg-frame")).toBe(true)
  expect(request.frames.every((frame, index) => index === 0 || frame.t_ms - request.frames[index - 1].t_ms >= 40)).toBe(true)
  expect(request.frames.at(-1)!.t_ms).toBeLessThanOrEqual(9000)
  expect(screen.getByText("Voz calibrada.")).toBeInTheDocument()
  expect(onCalibrated).toHaveBeenCalledWith("Voz calibrada.")
  expect(screen.getByRole("button", { name: "Calibrar de nuevo" })).toBeEnabled()
})

it("shows the server error message verbatim and lets the candidate retry", async () => {
  const message = "Tu voz no coincide con el movimiento de tus labios. Mirá la cámara, leé la frase en voz alta y repetí la calibración."
  const { submit } = setup()
  submit.mockRejectedValueOnce(new Error(message))
  begin()
  await elapse(9_500)
  expect(screen.getByRole("alert")).toHaveTextContent(message)
  expect(screen.getByText("Pendiente")).toBeInTheDocument()
  fireEvent.click(screen.getByRole("button", { name: "Reintentar" }))
  await elapse(9_500)
  expect(screen.getByText("Voz calibrada.")).toBeInTheDocument()
  expect(submit).toHaveBeenCalledTimes(2)
})

it("does not submit when the camera produced no frames", async () => {
  const { submit } = setup({ captureFrame: () => null })
  begin()
  await elapse(9_500)
  expect(screen.getByRole("alert")).toHaveTextContent(/video sincronizado/)
  expect(submit).not.toHaveBeenCalled()
})

it("does not submit when the microphone produced nothing or there is no recording", async () => {
  const empty = setup({ recorder: { start: vi.fn(), stop: () => ({ samples: [], startedAt: 1 }) } })
  begin()
  await elapse(9_500)
  expect(screen.getByRole("alert")).toHaveTextContent(/No se pudo capturar el micrófono/)
  expect(empty.submit).not.toHaveBeenCalled()
  cleanup()
  const none = setup({ recorder: { start: vi.fn(), stop: () => null } })
  begin()
  await elapse(9_500)
  expect(screen.getByRole("alert")).toHaveTextContent(/No se pudo capturar el micrófono/)
  expect(none.submit).not.toHaveBeenCalled()
})

it("ignores a second click while recording and honors disabled", async () => {
  const { start, submit } = setup()
  begin()
  expect(screen.getByRole("button", { name: "Calibrando…" })).toBeDisabled()
  await elapse(9_500)
  expect(submit).toHaveBeenCalledTimes(1)
  expect(start).toHaveBeenCalledTimes(1)
  cleanup()
  setup({ disabled: true })
  expect(screen.getByRole("button", { name: "Empezar calibración de voz" })).toBeDisabled()
})

it("stops the recording, the frame timer and sends nothing when it is unmounted midway", async () => {
  const { start, stop, submit, captureFrame } = setup()
  begin()
  expect(start).toHaveBeenCalled()
  await elapse(1_000)
  cleanup()
  const grabbed = captureFrame.mock.calls.length
  await elapse(10_000)
  expect(stop).toHaveBeenCalled()
  expect(submit).not.toHaveBeenCalled()
  expect(captureFrame.mock.calls.length).toBe(grabbed)
  expect(vi.getTimerCount()).toBe(0)
})

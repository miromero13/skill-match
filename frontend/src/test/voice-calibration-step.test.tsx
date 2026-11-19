import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"
import {
  VOICE_PHRASE,
  VoiceCalibrationStep,
  type VoiceCalibrationStepProps,
} from "@/components/integrity/voice-calibration-step"

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

function setup(overrides: Partial<VoiceCalibrationStepProps> = {}) {
  const start = vi.fn()
  const stop = vi.fn(() => ({ samples: [0.1, -0.1, 0.2], startedAt: 5_000 }))
  const readMouth = vi.fn(() => [{ t_ms: 100, mouth_open: 0.2 }])
  const submit = vi.fn<VoiceCalibrationStepProps["submit"]>(async () => ({ message: "Voz calibrada." }))
  const onCalibrated = vi.fn()
  render(
    <VoiceCalibrationStep
      recorder={{ start, stop }}
      readMouth={readMouth}
      submit={submit}
      onCalibrated={onCalibrated}
      ambientMs={20}
      phraseMs={40}
      tickMs={5}
      {...overrides}
    />,
  )
  return { start, stop, readMouth, submit, onCalibrated }
}

const begin = () => fireEvent.click(screen.getByRole("button", { name: "Empezar calibración de voz" }))

it("starts idle: nothing is recorded and the control phrase is not shown yet", () => {
  const { start, submit } = setup()
  expect(screen.getByText("Pendiente")).toBeInTheDocument()
  expect(screen.queryByTestId("voice-phrase")).not.toBeInTheDocument()
  expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  expect(start).not.toHaveBeenCalled()
  expect(submit).not.toHaveBeenCalled()
})

it("asks for silence first, then shows the control phrase to read aloud", async () => {
  vi.useFakeTimers()
  const { start } = setup({ ambientMs: 2000, phraseMs: 7000, tickMs: 250 })
  begin()
  expect(start).toHaveBeenCalledTimes(1)
  expect(screen.getByTestId("voice-calibration-status")).toHaveTextContent(/Quedate en silencio/)
  expect(screen.getByTestId("voice-calibration-status")).toHaveTextContent("2 s")
  expect(screen.queryByTestId("voice-phrase")).not.toBeInTheDocument()
  await act(async () => {
    await vi.advanceTimersByTimeAsync(2100)
  })
  expect(screen.getByTestId("voice-phrase")).toHaveTextContent(VOICE_PHRASE)
  expect(screen.getByTestId("voice-calibration-status")).toHaveTextContent(/Leé en voz alta/)
})

it("posts the 16 kHz audio, the silence length and the mouth telemetry and shows the server message verbatim", async () => {
  const { start, stop, readMouth, submit, onCalibrated } = setup()
  begin()
  await waitFor(() => expect(submit).toHaveBeenCalledTimes(1))
  expect(start).toHaveBeenCalledTimes(1)
  expect(stop).toHaveBeenCalledTimes(1)
  // The mouth readings are asked for the whole recording: from where the audio started, silence included.
  expect(readMouth).toHaveBeenCalledWith(5_000, 60)
  expect(submit).toHaveBeenCalledWith({
    audio_samples: [0.1, -0.1, 0.2],
    ambient_ms: 20,
    mouth_samples: [{ t_ms: 100, mouth_open: 0.2 }],
  })
  expect(await screen.findByText("Voz calibrada.")).toBeInTheDocument()
  expect(onCalibrated).toHaveBeenCalledWith("Voz calibrada.")
  expect(screen.getByText("Calibrada")).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "Calibrar de nuevo" })).toBeEnabled()
})

it("shows the server error message verbatim and lets the candidate retry", async () => {
  const message = "Tu voz no coincide con el movimiento de tus labios. Mirá la cámara, leé la frase en voz alta y repetí la calibración."
  const { submit } = setup()
  submit.mockRejectedValueOnce(new Error(message))
  begin()
  expect(await screen.findByRole("alert")).toHaveTextContent(message)
  expect(screen.getByText("Pendiente")).toBeInTheDocument()
  fireEvent.click(screen.getByRole("button", { name: "Reintentar" }))
  expect(await screen.findByText("Voz calibrada.")).toBeInTheDocument()
  expect(submit).toHaveBeenCalledTimes(2)
})

it("does not submit when the microphone produced nothing", async () => {
  const { submit } = setup({ recorder: { start: vi.fn(), stop: () => ({ samples: [], startedAt: 1 }) } })
  begin()
  expect(await screen.findByRole("alert")).toHaveTextContent(/No se pudo capturar el micrófono/)
  expect(submit).not.toHaveBeenCalled()
})

it("does not submit when there is no recording at all", async () => {
  const { submit } = setup({ recorder: { start: vi.fn(), stop: () => null } })
  begin()
  expect(await screen.findByRole("alert")).toHaveTextContent(/No se pudo capturar el micrófono/)
  expect(submit).not.toHaveBeenCalled()
})

it("ignores a second click while recording and honors disabled", async () => {
  const { start, submit } = setup()
  begin()
  expect(screen.getByRole("button", { name: "Calibrando…" })).toBeDisabled()
  await waitFor(() => expect(submit).toHaveBeenCalledTimes(1))
  expect(start).toHaveBeenCalledTimes(1)
  cleanup()
  setup({ disabled: true })
  expect(screen.getByRole("button", { name: "Empezar calibración de voz" })).toBeDisabled()
})

it("stops the recording and sends nothing when it is unmounted midway", async () => {
  vi.useFakeTimers()
  const { start, stop, submit } = setup({ ambientMs: 2000, phraseMs: 7000, tickMs: 250 })
  begin()
  expect(start).toHaveBeenCalled()
  cleanup()
  await vi.advanceTimersByTimeAsync(10_000)
  expect(stop).toHaveBeenCalled()
  expect(submit).not.toHaveBeenCalled()
})

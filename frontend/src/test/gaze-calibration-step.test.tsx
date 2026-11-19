import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"
import {
  GAZE_TARGETS,
  GazeCalibrationStep,
  type GazeCalibrationStepProps,
} from "@/components/integrity/gaze-calibration-step"

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

function setup(overrides: Partial<GazeCalibrationStepProps> = {}) {
  let frame = 0
  const captureFrame = vi.fn(() => `data:image/jpeg;base64,F${frame++}`)
  const submit = vi.fn<GazeCalibrationStepProps["submit"]>(async () => ({ message: "Zona de mirada calibrada." }))
  const onCalibrated = vi.fn()
  render(
    <GazeCalibrationStep
      captureFrame={captureFrame}
      submit={submit}
      onCalibrated={onCalibrated}
      settleMs={10}
      frameIntervalMs={5}
      {...overrides}
    />,
  )
  return { captureFrame, submit, onCalibrated }
}

const start = () => fireEvent.click(screen.getByRole("button", { name: "Empezar calibración" }))

it("starts idle: five dots, nothing captured and no alert", () => {
  const { captureFrame, submit } = setup()
  expect(GAZE_TARGETS).toEqual(["CENTER", "TOP_LEFT", "TOP_RIGHT", "BOTTOM_LEFT", "BOTTOM_RIGHT"])
  for (const target of GAZE_TARGETS) expect(screen.getByTestId(`gaze-dot-${target}`)).toBeInTheDocument()
  expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  expect(captureFrame).not.toHaveBeenCalled()
  expect(submit).not.toHaveBeenCalled()
  expect(screen.getByText("Pendiente")).toBeInTheDocument()
})

it("guides the candidate through the center and the four corners and submits three frames each", async () => {
  const { captureFrame, submit, onCalibrated } = setup()
  start()
  await waitFor(() => expect(submit).toHaveBeenCalledTimes(1))
  const points = submit.mock.calls[0][0]
  expect(points.map((point) => point.target)).toEqual([...GAZE_TARGETS])
  expect(points.every((point) => point.frames.length === 3)).toBe(true)
  expect(new Set(points.flatMap((point) => point.frames)).size).toBe(15) // fresh frames, not one reused
  expect(captureFrame).toHaveBeenCalledTimes(15)
  expect(await screen.findByText("Zona de mirada calibrada.")).toBeInTheDocument()
  expect(onCalibrated).toHaveBeenCalledWith("Zona de mirada calibrada.")
  expect(screen.getByText("Calibrada")).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "Calibrar de nuevo" })).toBeEnabled()
})

it("highlights the dot of the current target while capturing", async () => {
  vi.useFakeTimers()
  setup({ settleMs: 100, frameIntervalMs: 10 })
  start()
  expect(screen.getByTestId("gaze-dot-CENTER")).toHaveAttribute("data-active", "true")
  expect(screen.getByTestId("gaze-dot-TOP_LEFT")).toHaveAttribute("data-active", "false")
  expect(screen.getByTestId("gaze-calibration-status")).toHaveTextContent("Punto 1 de 5: Mirá el punto del centro de la pantalla.")
  await act(async () => {
    await vi.advanceTimersByTimeAsync(135)
  })
  expect(screen.getByTestId("gaze-dot-TOP_LEFT")).toHaveAttribute("data-active", "true")
  expect(screen.getByTestId("gaze-calibration-status")).toHaveTextContent("Punto 2 de 5: Mirá la esquina superior izquierda.")
  expect(screen.getByRole("button", { name: "Calibrando…" })).toBeDisabled()
})

it("shows the server error message verbatim and allows a retry", async () => {
  const message = "No pudimos distinguir hacia dónde mirabas. Mirá cada punto moviendo los ojos o la cabeza hacia esa esquina y repetí la calibración."
  const { submit } = setup()
  submit.mockRejectedValueOnce(new Error(message))
  start()
  expect(await screen.findByRole("alert")).toHaveTextContent(message)
  expect(screen.getByText("Pendiente")).toBeInTheDocument()
  fireEvent.click(screen.getByRole("button", { name: "Reintentar" }))
  expect(await screen.findByText("Zona de mirada calibrada.")).toBeInTheDocument()
  expect(submit).toHaveBeenCalledTimes(2)
})

it("does not submit when the camera never delivers frames", async () => {
  const camera = vi.fn((): string | null => null)
  const { submit } = setup({ captureFrame: camera })
  start()
  expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo capturar la cámara.")
  expect(submit).not.toHaveBeenCalled()
  expect(camera).toHaveBeenCalledTimes(12) // 3 frames x 4 attempts, then it gives up on the first target
})

it("cannot be started while disabled", () => {
  setup({ disabled: true })
  expect(screen.getByRole("button", { name: "Empezar calibración" })).toBeDisabled()
})

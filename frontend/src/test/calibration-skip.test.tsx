import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom"
import { CalibrationPanel } from "@/components/evaluations/calibration-panel"
import { skipEvaluationCalibration } from "@/services/evaluation-service"

vi.mock("@/services/evaluation-service", () => ({
  requestCalibrationChallenge: vi.fn(),
  verifyEvaluationCalibration: vi.fn(),
  skipEvaluationCalibration: vi.fn(),
}))

function Theory() {
  const location = useLocation()
  return <p>Examen {location.pathname}{location.search}</p>
}

function showPanel(skipAllowed: boolean) {
  return render(
    <MemoryRouter initialEntries={["/evaluation/offer-1/setup"]}>
      <Routes>
        <Route path="/evaluation/offer-1/setup" element={<CalibrationPanel evaluationId="evaluation-1" targetLevel={3} skipAllowed={skipAllowed} />} />
        <Route path="/evaluation/:id/theory" element={<Theory />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(skipEvaluationCalibration).mockResolvedValue({
    evaluation_id: "evaluation-1", ready: true, skipped: true, status: "READY_FOR_THEORY", started_at: null, checks: {},
  })
})
afterEach(cleanup)

describe("calibration skip for field testing", () => {
  it("renders nothing new when the backend does not allow skipping", () => {
    showPanel(false)
    expect(screen.queryByRole("checkbox", { name: "Saltar calibración (modo pruebas)" })).not.toBeInTheDocument()
    expect(screen.queryByText("Solo para pruebas en ambientes con ruido.")).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Comenzar primera prueba" })).toBeDisabled()
    expect(skipEvaluationCalibration).not.toHaveBeenCalled()
  })

  it("checking the box enables continuing, calls the skip service and opens the exam", async () => {
    const user = userEvent.setup()
    showPanel(true)
    expect(screen.getByText("Solo para pruebas en ambientes con ruido.")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Comenzar primera prueba" })).toBeDisabled()
    expect(screen.queryByRole("button", { name: "Continuar sin calibración" })).not.toBeInTheDocument()

    await user.click(screen.getByRole("checkbox", { name: "Saltar calibración (modo pruebas)" }))
    const proceed = screen.getByRole("button", { name: "Continuar sin calibración" })
    expect(proceed).toBeEnabled()
    expect(skipEvaluationCalibration).not.toHaveBeenCalled()

    await user.click(proceed)
    expect(skipEvaluationCalibration).toHaveBeenCalledWith("evaluation-1")
    expect(await screen.findByText("Examen /evaluation/evaluation-1/theory?level=3")).toBeInTheDocument()
  })

  it("stays on calibration when the skip request fails", async () => {
    vi.mocked(skipEvaluationCalibration).mockRejectedValue(new Error("Recurso no encontrado"))
    const user = userEvent.setup()
    showPanel(true)
    await user.click(screen.getByRole("checkbox", { name: "Saltar calibración (modo pruebas)" }))
    await user.click(screen.getByRole("button", { name: "Continuar sin calibración" }))
    expect(skipEvaluationCalibration).toHaveBeenCalledTimes(1)
    expect(await screen.findByRole("button", { name: "Continuar sin calibración" })).toBeEnabled()
    expect(screen.queryByText(/^Examen /)).not.toBeInTheDocument()
  })
})

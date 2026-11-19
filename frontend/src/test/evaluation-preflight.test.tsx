import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { EvaluationSetupPage } from "@/pages/evaluation-setup-page"
import { useEvaluationPreflightStore } from "@/stores/evaluation-preflight-store"
import {
  getEvaluationPreflight,
  registerEvaluationConsent,
  type EvaluationPreflight,
} from "@/services/evaluation-service"

vi.mock("@/services/evaluation-service", () => ({
  getEvaluationPreflight: vi.fn(),
  registerEvaluationConsent: vi.fn(),
  requestCalibrationChallenge: vi.fn(),
  verifyEvaluationCalibration: vi.fn(),
}))

const preflight: EvaluationPreflight = {
  teaching_skill_id: "offer-1",
  skill_name: "Python",
  declared_level: "INTERMEDIATE",
  declared_level_label: "Nivel 3 · Intermedio",
  target_level_number: 3,
  syllabus: "Fundamentos",
  requirements: ["Cámara y micrófono disponibles"],
  stages: ["Teoría", "Práctica de la habilidad", "Defensa con preguntas"],
  estimated_duration_minutes: 25,
  free_evaluations_left: 3,
  attempts_used: 0,
  policy_version: "v1.0",
  pending_evaluation_id: null,
}

function showPage() {
  return render(
    <MemoryRouter initialEntries={["/evaluation/offer-1/setup"]}>
      <Routes>
        <Route path="/evaluation/:skillId/setup" element={<EvaluationSetupPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  useEvaluationPreflightStore.getState().reset()
  vi.mocked(getEvaluationPreflight).mockResolvedValue(preflight)
  vi.mocked(registerEvaluationConsent).mockResolvedValue({
    id: "evaluation-1",
    status: "PENDING_CALIBRATION",
    biometric_consent_at: "2026-11-18T00:00:00Z",
    policy_version: "v1.0",
    started_at: null,
  })
})

afterEach(cleanup)

describe("shared evaluation preparation", () => {
  it("reading instructions does not register consent or start an attempt", async () => {
    showPage()
    expect(await screen.findByRole("heading", { name: "Validar Python" })).toBeInTheDocument()
    expect(screen.getByRole("navigation", { name: "Pasos del pre-embarque" })).toHaveTextContent("Calibración")
    expect(screen.getByText("Paso 1 de 3")).toBeInTheDocument()
    expect(getEvaluationPreflight).toHaveBeenCalledWith("offer-1")
    expect(screen.getByLabelText("Habilidad declarada en tu perfil")).toHaveValue("Python")
    expect(screen.getByLabelText("Habilidad declarada en tu perfil")).toBeDisabled()
    expect(screen.getByLabelText("Nivel objetivo a validar")).toHaveValue("Nivel 3 · Intermedio")
    expect(screen.getByLabelText("Nivel objetivo a validar")).toBeDisabled()
    expect(screen.getByLabelText("Duración estimada")).toHaveValue("25 minutos")
    expect(screen.getByLabelText("Duración estimada")).toBeDisabled()
    expect(screen.getByText("Teoría")).toBeInTheDocument()
    expect(screen.getByText("Práctica de la habilidad")).toBeInTheDocument()
    expect(screen.getByText("Defensa con preguntas")).toBeInTheDocument()
    expect(screen.getByText(/Leer las instrucciones y aceptar el consentimiento no consume/)).toBeInTheDocument()
    expect(screen.getByText(/Habilidades gratuitas disponibles: 3\/3/)).toBeInTheDocument()
    expect(registerEvaluationConsent).not.toHaveBeenCalled()
  })

  it("requires every consent and confirms preparation without spending the attempt", async () => {
    const user = userEvent.setup()
    showPage()
    await user.click(await screen.findByRole("button", { name: "Siguiente: normas de integridad" }))
    const continueButton = screen.getByRole("button", { name: "Registrar consentimiento" })
    expect(continueButton).toBeDisabled()
    await user.click(screen.getByRole("checkbox", { name: /Acepto el procesamiento biométrico/ }))
    await user.click(screen.getByRole("checkbox", { name: /Acepto las normas de integridad/ }))
    expect(continueButton).toBeDisabled()
    await user.click(screen.getByRole("checkbox", { name: /Entiendo que al comenzar el examen/ }))
    await user.click(continueButton)
    await waitFor(() => expect(registerEvaluationConsent).toHaveBeenCalledTimes(1))
    expect(registerEvaluationConsent).toHaveBeenCalledWith("offer-1", {
      biometric_consent: true,
      integrity_consent: true,
      attempt_rule_accepted: true,
      policy_version: "v1.0",
    })
    expect(await screen.findByText(/El intento todavía no comenzó ni se descontó/)).toBeInTheDocument()
    expect(screen.getByText("Paso 3 de 3")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Preparar cámara y micrófono" })).toBeInTheDocument()
    expect(screen.getByText(/Habilidades gratuitas disponibles: 3\/3/)).toBeInTheDocument()
    expect(useEvaluationPreflightStore.getState().preflight?.free_evaluations_left).toBe(3)
    expect(useEvaluationPreflightStore.getState().consent?.started_at).toBeNull()
  })

  it("shows the backend rejection without creating consent", async () => {
    const message = "Debe registrar su rostro testigo en su perfil antes de solicitar una certificación"
    vi.mocked(getEvaluationPreflight).mockRejectedValue(new Error(message))
    showPage()
    expect(await screen.findByRole("alert")).toHaveTextContent(message)
    expect(screen.getByRole("link", { name: "Ir a mi perfil" })).toHaveAttribute("href", "/app/profile")
    expect(screen.queryByRole("button", { name: "Registrar consentimiento" })).not.toBeInTheDocument()
    expect(registerEvaluationConsent).not.toHaveBeenCalled()
  })
})

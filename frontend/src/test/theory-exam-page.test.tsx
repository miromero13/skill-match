import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { TheoryExamPage } from "@/pages/theory-exam-page"
import { useTheoryExamStore } from "@/stores/theory-exam-store"
import { startOralRecording } from "@/services/oral-recording"
import { ApiError } from "@/types/api"

const api = vi.hoisted(() => ({ status: vi.fn(), start: vi.fn(), answer: vi.fn(), retryGrading: vi.fn(), cancel: vi.fn() }))
vi.mock("@/services/theory-exam-service", () => ({ theoryExam: api }))
vi.mock("@/services/oral-recording", () => ({ startOralRecording: vi.fn() }))
const question = { id: "question", version: 1, position: 1, kind: "OPEN", prompt: "Explain mutability", choices: [], time_limit_seconds: 90, max_score: 20 }
const state = { evaluation_id: "exam", status: "THEORY_ACTIVE", question_count: 5, answered_count: 0, position: 1,
  server_time: new Date().toISOString(), deadline_at: new Date(Date.now() + 600000).toISOString(),
  question_deadline_at: new Date(Date.now() + 90000).toISOString(), current_question: question }
afterEach(() => vi.restoreAllMocks())
const mount = () => render(
  <MemoryRouter initialEntries={["/evaluation/exam/theory"]}>
    <Routes>
      <Route path="/evaluation/:id/theory" element={<TheoryExamPage />} />
      <Route path="/evaluation/:id/code" element={<div>Programming Phase</div>} />
      <Route path="/evaluation/:id/result" element={<div>Final Result Phase</div>} />
      <Route path="/app/teaching-skills" element={<div>Teaching Skills</div>} />
    </Routes>
  </MemoryRouter>
)
beforeEach(() => {
  vi.resetAllMocks()
  useTheoryExamStore.getState().setProgress(null)
  api.status.mockResolvedValue({ data: state, message: "Estado del examen recuperado exitosamente." })
})
it("shows the server question and oral justification instruction without typed answers", async () => {
  mount()
  expect(await screen.findByText("Explain mutability")).toBeInTheDocument()
  expect(screen.getByText(/Respondé hablando y justificá/)).toBeInTheDocument()
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument()
  expect(screen.getByRole("button", { name: "Grabar respuesta" })).toBeEnabled()
  expect(screen.getByRole("timer")).toBeInTheDocument()
})
it("auto-starts on 409 without a second consent prompt and preserves backend start errors", async () => {
  api.status.mockRejectedValue(new ApiError("El examen teórico todavía no comenzó.", 409))
  api.start.mockRejectedValue(new ApiError("La transcripción local no está disponible. Tu respuesta no fue registrada.", 503))
  mount()
  await waitFor(() => expect(api.start).toHaveBeenCalledWith("exam", 1, true))
  expect(await screen.findByRole("alert")).toHaveTextContent("La transcripción local no está disponible. Tu respuesta no fue registrada.")
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument()
  expect(screen.queryByText("Explain mutability")).not.toBeInTheDocument()
})
it("redirects directly to the programming phase when theory questions finish and has_coding_stage is true", async () => {
  api.status.mockResolvedValue({ data: { ...state, status: "THEORY_PENDING_REVIEW", current_question: null, question_deadline_at: null, answered_count: 5, has_coding_stage: true } })
  mount()
  expect(await screen.findByText("Programming Phase")).toBeInTheDocument()
})
it("redirects directly to final result when theory questions finish and has_coding_stage is false", async () => {
  api.status.mockResolvedValue({ data: { ...state, status: "THEORY_PENDING_REVIEW", current_question: null, question_deadline_at: null, answered_count: 5, has_coding_stage: false } })
  mount()
  expect(await screen.findByText("Final Result Phase")).toBeInTheDocument()
})
it("cancels the evaluation and exits to teaching-skills", async () => {
  const user = userEvent.setup()
  api.cancel.mockResolvedValue({ data: { evaluation_id: "exam", status: "CANCELLED" }, message: "Evaluación cancelada." })
  mount()
  await screen.findByText("Explain mutability")
  await user.click(screen.getByRole("button", { name: "Cancelar evaluación" }))
  await waitFor(() => expect(api.cancel).toHaveBeenCalledWith("exam"))
  expect(await screen.findByText("Teaching Skills")).toBeInTheDocument()
})

it("keeps the same oral submission ID and audio for a network retry", async () => {
  const user = userEvent.setup()
  const track = { readyState: "live", stop: vi.fn(), addEventListener: vi.fn() }
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: {
    getUserMedia: vi.fn(async () => ({ getTracks: () => [track], getVideoTracks: () => [track] })),
  } })
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined)
  vi.mocked(startOralRecording).mockResolvedValue({ stop: vi.fn(async () => "PCM_WAV_PAYLOAD"), cancel: vi.fn() })
  api.answer.mockRejectedValueOnce(new Error("Se interrumpió la red."))
    .mockResolvedValueOnce({ data: { transcript: "Lists are mutable" }, message: "Respuesta oral registrada exitosamente." })
  const view = mount()
  await screen.findByText("Explain mutability")
  await waitFor(() => expect(screen.getByRole("button", { name: "Grabar respuesta" })).toBeEnabled())
  await user.click(screen.getByRole("button", { name: "Grabar respuesta" }))
  await user.click(screen.getByRole("button", { name: "Terminar y enviar respuesta" }))
  expect(await screen.findByRole("alert")).toHaveTextContent("Se interrumpió la red.")
  await user.click(screen.getByRole("button", { name: "Reenviar misma respuesta" }))
  await screen.findByText("Respuesta oral registrada exitosamente.")
  expect(api.answer).toHaveBeenCalledTimes(2)
  expect(api.answer.mock.calls[0]).toEqual(api.answer.mock.calls[1])
  expect(api.answer.mock.calls[0][1]).toEqual(expect.objectContaining({ question_id: "question", audio_base64: "PCM_WAV_PAYLOAD" }))
  view.unmount()
})

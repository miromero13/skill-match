import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { TheoryExamPage } from "@/pages/theory-exam-page"
import { useTheoryExamStore } from "@/stores/theory-exam-store"
import { startOralRecording } from "@/services/oral-recording"

const api = vi.hoisted(() => ({ status: vi.fn(), start: vi.fn(), answer: vi.fn() }))
vi.mock("@/services/theory-exam-service", () => ({ theoryExam: api }))
vi.mock("@/services/oral-recording", () => ({ startOralRecording: vi.fn() }))
const question = { id: "question", version: 1, position: 1, kind: "OPEN", prompt: "Explain mutability", choices: [], time_limit_seconds: 90, max_score: 20 }
const state = { evaluation_id: "exam", status: "THEORY_ACTIVE", question_count: 5, answered_count: 0, position: 1,
  server_time: new Date().toISOString(), deadline_at: new Date(Date.now() + 600000).toISOString(),
  question_deadline_at: new Date(Date.now() + 90000).toISOString(), current_question: question }
afterEach(() => vi.restoreAllMocks())
const mount = () => render(<MemoryRouter initialEntries={["/evaluation/exam/theory"]}><Routes><Route path="/evaluation/:id/theory" element={<TheoryExamPage />} /></Routes></MemoryRouter>)
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
  expect(screen.getByRole("button", { name: "Grabar respuesta" })).toBeDisabled()
})
it("preserves exact backend errors and does not claim an exam started", async () => {
  const user = userEvent.setup()
  api.status.mockRejectedValue(new Error("El examen teórico todavía no comenzó."))
  api.start.mockRejectedValue(new Error("La transcripción local no está disponible. Tu respuesta no fue registrada."))
  mount()
  expect(await screen.findByRole("alert")).toHaveTextContent("El examen teórico todavía no comenzó.")
  await user.click(screen.getByRole("button", { name: "Comenzar examen y consumir intento" }))
  expect(api.start).toHaveBeenCalledWith("exam", 1)
  expect(await screen.findByText("La transcripción local no está disponible. Tu respuesta no fue registrada.")).toBeInTheDocument()
  expect(screen.queryByText("Explain mutability")).not.toBeInTheDocument()
})
it("shows pending review, not a fabricated score or certification", async () => {
  api.status.mockResolvedValue({ data: { ...state, status: "THEORY_PENDING_REVIEW", current_question: null, question_deadline_at: null, answered_count: 5 } })
  mount()
  expect(await screen.findByText("Respuestas recibidas · corrección pendiente")).toBeInTheDocument()
  expect(screen.queryByRole("button", { name: "Grabar respuesta" })).not.toBeInTheDocument()
  expect(screen.queryByText(/Aprobado|100 puntos|Sello otorgado/)).not.toBeInTheDocument()
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
  await user.click(screen.getByRole("button", { name: "Activar cámara" }))
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
  expect(track.stop).toHaveBeenCalled()
})

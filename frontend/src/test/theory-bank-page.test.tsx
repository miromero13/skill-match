import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, expect, it, vi } from "vitest"
import { TheoryBankPage } from "@/pages/theory-bank-page"

const calls = vi.hoisted(() => ({ list: vi.fn(), create: vi.fn(), edit: vi.fn(), publish: vi.fn(), archive: vi.fn(), history: vi.fn() }))
vi.mock("@/services/theory-bank-service", () => ({ theoryBank: calls }))
vi.mock("@/services/admin-catalog-service", () => ({ getSkills: async () => ({ items: [{ id: "skill", name: "Python", levels: [{ level_number: 1, name: "Principiante" }] }], count: 1 }) }))
const item = { id: "question", version: 1, skill_id: "skill", level_number: 1, status: "DRAFT", content: {
  kind: "OPEN", prompt: "Explain mutability", choices: [], correct_choice: null,
  reference_answer: "Lists are mutable", criteria: [], time_limit_seconds: 90, max_score: 20,
} }
beforeEach(() => {
  vi.resetAllMocks()
  calls.list.mockResolvedValue({ data: [item], count: 1 })
  calls.history.mockResolvedValue({ data: [item], message: "Historial recuperado" })
  calls.create.mockResolvedValue({ data: item, message: "Borrador creado por el servidor" })
  calls.publish.mockResolvedValue({ data: { ...item, version: 2, status: "PUBLISHED" }, message: "Publicación confirmada por el servidor" })
})
it("loads questions and opens immutable history", async () => {
  const user = userEvent.setup()
  render(<TheoryBankPage />)
  expect(await screen.findByText("Explain mutability")).toBeInTheDocument()
  await user.click(screen.getByRole("button", { name: "Historial" }))
  expect(calls.history).toHaveBeenCalledWith("question")
  expect(await screen.findByText("Versión 1 · DRAFT")).toBeInTheDocument()
})
it("creates a draft and displays the exact server message", async () => {
  const user = userEvent.setup()
  render(<TheoryBankPage />)
  await screen.findByText("Explain mutability")
  await user.click(screen.getByRole("button", { name: "Nueva pregunta" }))
  await user.type(screen.getByLabelText("Enunciado"), "Explain tuples")
  await user.click(screen.getByRole("button", { name: "Guardar borrador" }))
  await waitFor(() => expect(calls.create).toHaveBeenCalledWith(expect.objectContaining({ skill_id: "skill", level_number: 1, prompt: "Explain tuples", kind: "OPEN" })))
  expect(await screen.findByText("Borrador creado por el servidor")).toBeInTheDocument()
})
it("publishes the current version and preserves server errors", async () => {
  const user = userEvent.setup()
  calls.publish.mockRejectedValueOnce(new Error("Completá la respuesta de referencia."))
  render(<TheoryBankPage />)
  await screen.findByText("Explain mutability")
  await user.click(screen.getByRole("button", { name: "Publicar" }))
  expect(calls.publish).toHaveBeenCalledWith("question", 1)
  expect(await screen.findByRole("alert")).toHaveTextContent("Completá la respuesta de referencia.")
  expect(screen.getByText("Explain mutability")).toBeInTheDocument()
})

it("edits with optimistic version and archives without deleting history", async () => {
  const user = userEvent.setup()
  calls.edit.mockResolvedValue({ data: { ...item, version: 2 }, message: "Nueva versión guardada por el servidor" })
  calls.archive.mockResolvedValue({ data: { ...item, status: "ARCHIVED" }, message: "Archivo confirmado por el servidor" })
  render(<TheoryBankPage />)
  await screen.findByText("Explain mutability")
  await user.click(screen.getByRole("button", { name: "Editar" }))
  await user.clear(screen.getByLabelText("Enunciado"))
  await user.type(screen.getByLabelText("Enunciado"), "Explain lists")
  await user.click(screen.getByRole("button", { name: "Guardar borrador" }))
  await waitFor(() => expect(calls.edit).toHaveBeenCalledWith("question", 1, expect.objectContaining({ prompt: "Explain lists" })))
  expect(await screen.findByText("Nueva versión guardada por el servidor")).toBeInTheDocument()
  await user.click(screen.getByRole("button", { name: "Archivar" }))
  expect(calls.archive).toHaveBeenCalledWith("question", 1)
  expect(await screen.findByText("Archivo confirmado por el servidor")).toBeInTheDocument()
})

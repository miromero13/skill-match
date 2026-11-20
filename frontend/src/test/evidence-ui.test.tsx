import { beforeEach, expect, it, vi } from "vitest"
import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { EvidenceManager } from "@/components/skill-evidences/evidence-manager"
import { EvidenceLinks } from "@/components/skill-evidences/evidence-links"
import { EvidenceForm } from "@/components/skill-evidences/evidence-form"
import { useSkillEvidenceStore } from "@/stores/skill-evidence-store"
import * as service from "@/services/skill-evidence-service"
import type { SkillEvidence } from "@/types/skill-evidence"

vi.mock("@/services/skill-evidence-service")
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }))
const item: SkillEvidence = {
  id: "e1",
  teaching_skill_id: "a",
  title: "Proyecto Python",
  description: "Mi proyecto",
  url: "https://example.com/",
  evidence_type: "REPOSITORY",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
}
const list = (items: SkillEvidence[]) => ({
  statuscode: 200,
  message: "Evidencias recuperadas exitosamente.",
  data: items,
  count: items.length,
})
beforeEach(() => {
  vi.resetAllMocks()
  useSkillEvidenceStore.getState().reset()
  vi.mocked(service.getEvidences).mockResolvedValue(list([]))
})

it("opens from a skill card and creates a normalized evidence", async () => {
  const user = userEvent.setup()
  vi.mocked(service.getEvidences)
    .mockResolvedValueOnce(list([]))
    .mockResolvedValue(list([item]))
  vi.mocked(service.createEvidence).mockResolvedValue({
    statuscode: 201,
    message: "Evidencia registrada exitosamente.",
    data: item,
  })
  render(<EvidenceManager skill={{ id: "a", skill_name: "Python" }} />)
  await user.click(screen.getByRole("button", { name: "Evidencias" }))
  expect(
    await screen.findByText(/Todavía no hay evidencias/)
  ).toBeInTheDocument()
  await user.click(screen.getByRole("button", { name: "Agregar evidencia" }))
  await user.type(screen.getByLabelText("Título"), "  Proyecto Python  ")
  await user.type(
    screen.getByLabelText("URL del recurso"),
    "https://example.com"
  )
  await user.click(screen.getByRole("button", { name: "Guardar evidencia" }))
  expect(await screen.findByText("Proyecto Python")).toBeInTheDocument()
  expect(service.createEvidence).toHaveBeenCalledWith("a", {
    title: "Proyecto Python",
    description: null,
    url: "https://example.com/",
    evidence_type: "REPOSITORY",
  })
})
it("preserves fields and shows the exact server error on conflict", async () => {
  const user = userEvent.setup()
  vi.mocked(service.createEvidence).mockRejectedValue(
    new Error("Ya registraste esta evidencia.")
  )
  render(<EvidenceManager skill={{ id: "a", skill_name: "Python" }} />)
  await user.click(screen.getByRole("button", { name: "Evidencias" }))
  await user.click(
    await screen.findByRole("button", { name: "Agregar evidencia" })
  )
  await user.type(screen.getByLabelText("Título"), "Project")
  await user.type(
    screen.getByLabelText("URL del recurso"),
    "https://example.com"
  )
  await user.click(screen.getByRole("button", { name: "Guardar evidencia" }))
  expect(
    await screen.findByText("Ya registraste esta evidencia.")
  ).toBeInTheDocument()
  expect(screen.getByLabelText("Título")).toHaveValue("Project")
})
it("requires explicit confirmation before deleting", async () => {
  const user = userEvent.setup()
  vi.mocked(service.getEvidences)
    .mockResolvedValueOnce(list([item]))
    .mockResolvedValue(list([]))
  vi.mocked(service.deleteEvidence).mockResolvedValue({
    statuscode: 200,
    message: "Eliminada",
    data: null,
  })
  render(<EvidenceManager skill={{ id: "a", skill_name: "Python" }} />)
  await user.click(screen.getByRole("button", { name: "Evidencias" }))
  await user.click(
    await screen.findByRole("button", { name: "Eliminar Proyecto Python" })
  )
  await user.click(
    within(screen.getByRole("alertdialog")).getByRole("button", {
      name: "Cancelar",
    })
  )
  expect(service.deleteEvidence).not.toHaveBeenCalled()
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Eliminar Proyecto Python" })
    ).toHaveFocus()
  )
  await user.click(
    screen.getByRole("button", { name: "Eliminar Proyecto Python" })
  )
  await user.click(
    within(screen.getByRole("alertdialog")).getByRole("button", {
      name: "Confirmar eliminación",
    })
  )
  await waitFor(() =>
    expect(service.deleteEvidence).toHaveBeenCalledWith("a", "e1")
  )
  expect(
    await screen.findByText(/Todavía no hay evidencias/)
  ).toBeInTheDocument()
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Agregar evidencia" })
    ).toHaveFocus()
  )
})
it("renders safe external links and never executes HTML as markup", () => {
  render(
    <EvidenceLinks
      items={[
        { ...item, title: "<script>bad()</script>" },
        { ...item, id: "e2", url: "javascript:bad()" },
      ]}
    />
  )
  const link = screen.getByRole("link")
  expect(link).toHaveAttribute("rel", "noopener noreferrer")
  expect(link).toHaveAttribute("target", "_blank")
  expect(screen.getByText("<script>bad()</script>")).toBeInTheDocument()
  expect(document.querySelector("script")).toBeNull()
  expect(screen.getByText("Enlace no disponible")).toBeInTheDocument()
})
it("validates locally and does not submit unsafe input", async () => {
  const save = vi.fn()
  const user = userEvent.setup()
  render(<EvidenceForm saving={false} onSave={save} onCancel={() => {}} />)
  await user.type(screen.getByLabelText("URL del recurso"), "javascript:bad()")
  await user.click(screen.getByRole("button", { name: "Guardar evidencia" }))
  expect(screen.getByLabelText("Título")).toHaveAttribute(
    "aria-invalid",
    "true"
  )
  expect(screen.getByLabelText("Título")).toHaveFocus()
  expect(save).not.toHaveBeenCalled()
})

it("edits using a complete PUT body and clears the description", async () => {
  const user = userEvent.setup()
  vi.mocked(service.getEvidences).mockResolvedValue(list([item]))
  vi.mocked(service.updateEvidence).mockResolvedValue({
    statuscode: 200,
    message: "Actualizada",
    data: { ...item, description: null },
  })
  render(<EvidenceManager skill={{ id: "a", skill_name: "Python" }} />)
  await user.click(screen.getByRole("button", { name: "Evidencias" }))
  await user.click(
    await screen.findByRole("button", { name: "Editar Proyecto Python" })
  )
  await user.clear(screen.getByLabelText(/Descripción/))
  await user.click(screen.getByRole("button", { name: "Guardar evidencia" }))
  await waitFor(() =>
    expect(service.updateEvidence).toHaveBeenCalledWith("a", "e1", {
      title: item.title,
      description: null,
      url: item.url,
      evidence_type: item.evidence_type,
    })
  )
})

it("restores keyboard focus to the skill action when closing", async () => {
  const user = userEvent.setup()
  render(<EvidenceManager skill={{ id: "a", skill_name: "Python" }} />)
  const trigger = screen.getByRole("button", { name: "Evidencias" })
  await user.click(trigger)
  expect(await screen.findByRole("dialog")).toBeInTheDocument()
  await user.keyboard("{Escape}")
  await waitFor(() => expect(trigger).toHaveFocus())
})

it("distinguishes a failed load from an empty list and supports retry", async () => {
  const user = userEvent.setup()
  vi.mocked(service.getEvidences)
    .mockRejectedValueOnce(new Error("No se pudo cargar el listado."))
    .mockResolvedValue(list([]))
  render(<EvidenceManager skill={{ id: "a", skill_name: "Python" }} />)
  await user.click(screen.getByRole("button", { name: "Evidencias" }))
  expect(
    await screen.findByText("No se pudo cargar el listado.")
  ).toBeInTheDocument()
  expect(
    screen.queryByText(/Todavía no hay evidencias/)
  ).not.toBeInTheDocument()
  await user.click(screen.getByRole("button", { name: "Reintentar" }))
  expect(
    await screen.findByText(/Todavía no hay evidencias/)
  ).toBeInTheDocument()
})

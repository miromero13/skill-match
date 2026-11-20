import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes, useParams } from "react-router-dom"
import { AdminCatalogPage } from "@/pages/admin-catalog-page"
import { useAdminCatalogStore } from "@/stores/admin-catalog-store"
import * as service from "@/services/admin-catalog-service"
import { skillLabApi } from "@/features/skill-lab/api/skill-lab-api"
import type { RubricCriterion, Skill } from "@/types/catalog"

vi.mock("@/services/admin-catalog-service", () => ({
  getCategories: vi.fn(), createCategory: vi.fn(), updateCategory: vi.fn(),
  getChallengeTypes: vi.fn(), createChallengeType: vi.fn(), getSkills: vi.fn(), getSkill: vi.fn(),
  createSkill: vi.fn(), updateSkill: vi.fn(), toggleSkillReady: vi.fn(), toggleSkillStatus: vi.fn(), deleteSkill: vi.fn(),
}))
vi.mock("@/features/skill-lab/api/skill-lab-api", () => ({
  skillLabApi: {
    getMetricTypes: vi.fn(), getConfig: vi.fn(), listSamples: vi.fn(), uploadSample: vi.fn(),
    deleteSample: vi.fn(), train: vi.fn(), listModels: vi.fn(), validate: vi.fn(),
  },
}))

const football = { id: "football", parent_id: null, name: "Fútbol", slug: "futbol", description: null, is_active: true }

function makeSkill(criteria: RubricCriterion[]): Skill {
  return {
    id: "skill-1",
    category_id: "football",
    challenge_type_id: null,
    name: "Dominadas",
    slug: "dominadas",
    description: null,
    min_approval_threshold: 80,
    is_ready_to_publish: false,
    is_active: true,
    levels: [
      { id: "lvl-1", level_number: 1, name: "Principiante", description: "", rubric: { min_score: 60, instructions: "", criteria } },
    ],
  }
}

function LabProbe() {
  const { skillId } = useParams()
  return <p>Laboratorio de {skillId}</p>
}

function renderCatalog() {
  return render(
    <MemoryRouter initialEntries={["/admin/catalog"]}>
      <Routes>
        <Route path="/admin/catalog" element={<AdminCatalogPage />} />
        <Route path="/admin/skill-lab/:skillId" element={<LabProbe />} />
      </Routes>
    </MemoryRouter>
  )
}

async function openEdit(skill: Skill) {
  vi.mocked(service.getSkills).mockResolvedValue({ items: [skill], count: 1 })
  vi.mocked(service.getSkill).mockResolvedValue(skill)
  const user = userEvent.setup()
  renderCatalog()
  await user.click(await screen.findByRole("button", { name: /Editar y Rúbricas/ }))
  return user
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(service.getCategories).mockResolvedValue([football])
  vi.mocked(service.getChallengeTypes).mockResolvedValue([])
  vi.mocked(service.getSkills).mockResolvedValue({ items: [], count: 0 })
  vi.mocked(skillLabApi.getMetricTypes).mockResolvedValue([])
  useAdminCatalogStore.setState({ categories: [], challengeTypes: [], skills: [], totalSkills: 0, selectedCategoryId: null, searchTerm: "", readyFilter: "all", isSkillModalOpen: false, isCategoryModalOpen: false, isChallengeTypeModalOpen: false, editingSkill: null, isLoading: false, isSubmitting: false, error: null })
})

describe("AdminCatalogPage criteria configuration", () => {
  it("shows the running weights total and blocks saving until the level sums 100, preserving keys", async () => {
    const skill = makeSkill([
      { key: "k-posture", name: "Postura", weight: 60, description: "Postura estable", metric_type: "REFERENCE_REPLICATION", target: null },
      { name: "Legado", weight: 20, description: "" },
    ])
    const user = await openEdit(skill)

    expect(await screen.findByText("Total: 80% — debe sumar 100%")).toBeInTheDocument()
    expect(
      screen.getByText("Los porcentajes de los criterios del nivel «Principiante» deben sumar 100% (actual: 80%).")
    ).toBeInTheDocument()
    const save = screen.getByRole("button", { name: /Actualizar Habilidad/ })
    expect(save).toBeDisabled()

    const legacyWeight = screen.getByLabelText("Peso del criterio 2")
    await user.clear(legacyWeight)
    await user.type(legacyWeight, "40")
    expect(screen.getByText("Total: 100%")).toBeInTheDocument()
    expect(screen.queryByText(/deben sumar 100% \(actual/)).not.toBeInTheDocument()
    expect(save).toBeEnabled()

    vi.mocked(service.updateSkill).mockResolvedValue(skill)
    await user.click(save)
    await waitFor(() => expect(service.updateSkill).toHaveBeenCalledTimes(1))
    const payload = vi.mocked(service.updateSkill).mock.calls[0][1]
    expect(payload.levels?.[0].rubric?.criteria).toEqual([
      { key: "k-posture", name: "Postura", weight: 60, description: "Postura estable", metric_type: "REFERENCE_REPLICATION", target: null },
      { name: "Legado", weight: 40, description: "", metric_type: "REFERENCE_REPLICATION", target: null },
    ])
  })

  it("defaults a new criterion weight to the remaining percentage of the level", async () => {
    const user = userEvent.setup()
    renderCatalog()
    await user.click(await screen.findByRole("button", { name: /Nueva Habilidad/ }))
    await user.click(screen.getByRole("button", { name: "+ Agregar Criterio" }))
    expect(screen.getByLabelText("Peso del criterio 1")).toHaveValue(100)
    expect(screen.getByText("Total: 100%")).toBeInTheDocument()

    await user.clear(screen.getByLabelText("Peso del criterio 1"))
    await user.type(screen.getByLabelText("Peso del criterio 1"), "70")
    expect(screen.getByText("Total: 70% — debe sumar 100%")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "+ Agregar Criterio" }))
    expect(screen.getByLabelText("Peso del criterio 2")).toHaveValue(30)
    expect(screen.getByText("Total: 100%")).toBeInTheDocument()
  })

  it("sends the metric type and the required target in the payload", async () => {
    const skill = makeSkill([
      { key: "k-touch", name: "Toques", weight: 60, description: "", metric_type: "REFERENCE_REPLICATION", target: null },
      { key: "k-posture", name: "Postura", weight: 40, description: "", metric_type: "REFERENCE_REPLICATION", target: null },
    ])
    const user = await openEdit(skill)

    expect(screen.queryByLabelText("Objetivo (toques seguidos)")).not.toBeInTheDocument()
    await user.click(screen.getByRole("combobox", { name: "Tipo de medición del criterio 1" }))
    await user.click(await screen.findByRole("option", { name: "Toques seguidos con balón" }))

    const target = screen.getByLabelText("Objetivo (toques seguidos)")
    expect(
      screen.getByText("El criterio «Toques» del nivel «Principiante» necesita un objetivo de toques mayor a 0.")
    ).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Actualizar Habilidad/ })).toBeDisabled()

    await user.type(target, "15")
    vi.mocked(service.updateSkill).mockResolvedValue(skill)
    await user.click(screen.getByRole("button", { name: /Actualizar Habilidad/ }))
    await waitFor(() => expect(service.updateSkill).toHaveBeenCalledTimes(1))
    const [skillId, payload] = vi.mocked(service.updateSkill).mock.calls[0]
    expect(skillId).toBe("skill-1")
    expect(payload.levels?.[0].rubric?.criteria).toEqual([
      { key: "k-touch", name: "Toques", weight: 60, description: "", metric_type: "BALL_TOUCH_STREAK", target: 15 },
      { key: "k-posture", name: "Postura", weight: 40, description: "", metric_type: "REFERENCE_REPLICATION", target: null },
    ])
  })

  it("uses the metric types served by the backend when available", async () => {
    vi.mocked(skillLabApi.getMetricTypes).mockResolvedValue([
      { code: "REFERENCE_REPLICATION", name: "Replicar referencia (servidor)", description: "", requires_target: false, requires_reference: true },
      { code: "BALL_TOUCH_STREAK", name: "Racha de toques (servidor)", description: "", requires_target: true, requires_reference: false },
    ])
    const skill = makeSkill([{ key: "k", name: "Toques", weight: 100, description: "", metric_type: "REFERENCE_REPLICATION", target: null }])
    const user = await openEdit(skill)
    await user.click(screen.getByRole("combobox", { name: "Tipo de medición del criterio 1" }))
    expect(await screen.findByRole("option", { name: "Racha de toques (servidor)" })).toBeInTheDocument()
  })

  it("navigates to the skill lab from the saved skill card", async () => {
    vi.mocked(service.getSkills).mockResolvedValue({ items: [makeSkill([])], count: 1 })
    const user = userEvent.setup()
    renderCatalog()
    await user.click(await screen.findByRole("button", { name: "Enviar al laboratorio" }))
    expect(await screen.findByText("Laboratorio de skill-1")).toBeInTheDocument()
  })
})

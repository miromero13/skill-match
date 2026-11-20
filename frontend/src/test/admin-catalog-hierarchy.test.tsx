import "@testing-library/jest-dom/vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, expect, it, vi } from "vitest"
import { MemoryRouter } from "react-router-dom"
import { AdminCatalogPage } from "@/pages/admin-catalog-page"
import { useAdminCatalogStore } from "@/stores/admin-catalog-store"
import * as service from "@/services/admin-catalog-service"

vi.mock("@/services/admin-catalog-service", () => ({
  getCategories: vi.fn(), createCategory: vi.fn(), updateCategory: vi.fn(),
  getChallengeTypes: vi.fn(), createChallengeType: vi.fn(), getSkills: vi.fn(), getSkill: vi.fn(),
  createSkill: vi.fn(), updateSkill: vi.fn(), toggleSkillReady: vi.fn(), toggleSkillStatus: vi.fn(), deleteSkill: vi.fn(),
}))
// The catalog page now loads the skill-lab metric types and links to the lab (router required).
vi.mock("@/features/skill-lab/api/skill-lab-api", () => ({
  skillLabApi: { getMetricTypes: vi.fn().mockResolvedValue([]) },
}))
const music = { id: "music", parent_id: null, name: "Música", slug: "musica", description: null, is_active: true }
const guitar = { id: "guitar", parent_id: "music", name: "Guitarra", slug: "guitarra", description: null, is_active: true }
beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(service.getCategories).mockResolvedValue([music, guitar])
  vi.mocked(service.getChallengeTypes).mockResolvedValue([])
  vi.mocked(service.getSkills).mockResolvedValue({ items: [], count: 0 })
  useAdminCatalogStore.setState({ categories: [], skills: [], totalSkills: 0, selectedCategoryId: null, searchTerm: "", readyFilter: "all", isSkillModalOpen: false, isCategoryModalOpen: false, isChallengeTypeModalOpen: false, isLoading: false, isSubmitting: false, error: null })
})

it("shows hierarchical paths and creates a subcategory using its actual parent ID", async () => {
  const user = userEvent.setup()
  render(<MemoryRouter><AdminCatalogPage /></MemoryRouter>)
  await screen.findByRole("button", { name: "Música / Guitarra" })
  await user.click(screen.getByRole("button", { name: "+ Categoría" }))
  await user.type(screen.getByLabelText("Nombre de Categoría *"), "Instrumentos")
  await user.click(screen.getByRole("combobox", { name: "Categoría superior" }))
  await user.click(screen.getByRole("option", { name: "Música" }))
  vi.mocked(service.createCategory).mockResolvedValue({ ...music, id: "instruments", name: "Instrumentos", parent_id: "music" })
  await user.click(screen.getByRole("button", { name: "Crear Categoría" }))
  await waitFor(() => expect(service.createCategory).toHaveBeenCalledWith({ name: "Instrumentos", parent_id: "music", description: undefined, is_active: true }))
})

it("opens category editing with its existing parent and saves deactivation without deleting children", async () => {
  const user = userEvent.setup()
  render(<MemoryRouter><AdminCatalogPage /></MemoryRouter>)
  await user.click(await screen.findByRole("button", { name: "Editar categoría Música / Guitarra" }))
  expect(screen.getByLabelText("Nombre de Categoría *")).toHaveValue("Guitarra")
  expect(screen.getByRole("combobox", { name: "Categoría superior" })).toHaveTextContent("Música")
  await user.click(screen.getByRole("switch", { name: "Categoría activa" }))
  vi.mocked(service.updateCategory).mockResolvedValue({ ...guitar, is_active: false })
  await user.click(screen.getByRole("button", { name: "Guardar Categoría" }))
  await waitFor(() => expect(service.updateCategory).toHaveBeenCalledWith("guitar", { name: "Guitarra", parent_id: "music", description: undefined, is_active: false }))
  expect(useAdminCatalogStore.getState().categories).toHaveLength(2)
  expect(useAdminCatalogStore.getState().categories.find((item) => item.id === "guitar")?.is_active).toBe(false)
})

it("keeps the skill and total after a successful logical deactivation", async () => {
  const skill = { id: "python", category_id: "music", name: "Python", slug: "python", is_active: true, is_ready_to_publish: true, min_approval_threshold: 80, levels: [] }
  useAdminCatalogStore.setState({ skills: [skill], totalSkills: 1 })
  vi.mocked(service.deleteSkill).mockResolvedValue()
  expect(await useAdminCatalogStore.getState().deleteSkill("python")).toBe(true)
  expect(useAdminCatalogStore.getState().totalSkills).toBe(1)
  expect(useAdminCatalogStore.getState().skills).toEqual([{ ...skill, is_active: false }])
})

import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, expect, it, vi } from "vitest"
import { AddLearningSkillDialog } from "@/components/learning-skills/add-learning-skill-dialog"
import { TeachingSkillsSection } from "@/pages/teaching-skills-page"
import * as teachingService from "@/services/teaching-skill-service"
import { learningSkillService } from "@/services/learning-skill-service"
import { searchService } from "@/services/search-service"
import { useAuthStore, type UserProfile } from "@/stores/auth-store"
import { useLearningSkillStore } from "@/stores/learning-skill-store"
import type { Category } from "@/types/catalog"

vi.mock("@/services/teaching-skill-service")
vi.mock("@/services/learning-skill-service", () => ({
  learningSkillService: {
    getMyLearningSkills: vi.fn(),
    getAvailableCatalogSkills: vi.fn(),
    addLearningSkill: vi.fn(),
    updateLearningSkill: vi.fn(),
    deleteLearningSkill: vi.fn(),
  },
}))
vi.mock("@/services/search-service", () => ({
  searchService: {
    getCategories: vi.fn(),
    getSkills: vi.fn(),
    searchTutors: vi.fn(),
  },
}))

const member: UserProfile = {
  id: "member-1",
  fullName: "Miembro Prueba",
  email: "miembro@example.invalid",
  role: "MEMBER",
  skillPointsBalance: 0,
  reputationScore: 0,
  trustLevel: 0,
  isVerified: false,
}

const categories: Category[] = [
  { id: "cat-music", parent_id: null, name: "Música", slug: "musica", is_active: true },
  { id: "cat-strings", parent_id: "cat-music", name: "Cuerdas", slug: "cuerdas", is_active: true },
  { id: "cat-tech", parent_id: null, name: "Tecnología", slug: "tecnologia", is_active: true },
]

beforeEach(() => {
  vi.resetAllMocks()
  useAuthStore.getState().login(member, "token")
  vi.mocked(searchService.getCategories).mockResolvedValue(categories)
  vi.mocked(teachingService.getTeachingSkills).mockResolvedValue({
    statuscode: 200,
    message: "Loaded",
    count: 0,
    data: [],
  })
  vi.mocked(teachingService.getTeachingCatalog).mockResolvedValue([
    { id: "skill-guitar", name: "Guitarra", category_id: "cat-strings" },
    { id: "skill-python", name: "Python", category_id: "cat-tech" },
  ])
  useLearningSkillStore.setState({
    learningSkills: [],
    catalogSkills: [],
    categories: [],
    isLoading: false,
    isCatalogLoading: false,
    error: null,
  })
  vi.mocked(learningSkillService.getAvailableCatalogSkills).mockResolvedValue([
    { id: "skill-guitar", name: "Guitarra", slug: "guitarra", category_id: "cat-strings" },
    { id: "skill-python", name: "Python", slug: "python", category_id: "cat-tech" },
  ])
})

it("requires selecting a category before picking a teaching skill and filters by hierarchy", async () => {
  const user = userEvent.setup()
  render(
    <MemoryRouter>
      <TeachingSkillsSection />
    </MemoryRouter>,
  )

  await user.click(await screen.findByRole("button", { name: "Agregar habilidad" }))
  const skillSelect = screen.getByRole("combobox", { name: "Habilidad" })
  expect(skillSelect).toBeDisabled()

  await user.click(screen.getByRole("combobox", { name: "Categoría" }))
  await user.click(await screen.findByRole("option", { name: "Música" }))

  expect(skillSelect).toBeEnabled()
  await user.click(skillSelect)
  expect(await screen.findByRole("option", { name: "Guitarra" })).toBeInTheDocument()
  expect(screen.queryByRole("option", { name: "Python" })).not.toBeInTheDocument()
})

it("requires selecting a category before picking a learning skill", async () => {
  const user = userEvent.setup()
  render(<AddLearningSkillDialog />)

  await user.click(screen.getByRole("button", { name: /Agregar Habilidad a Aprender/i }))
  const skillSelect = await screen.findByRole("combobox", { name: /Habilidad del Catálogo Maestro/i })
  expect(skillSelect).toBeDisabled()

  await user.click(screen.getByRole("combobox", { name: /Categoría/i }))
  await user.click(await screen.findByRole("option", { name: "Tecnología" }))

  expect(skillSelect).toBeEnabled()
  await user.click(skillSelect)
  expect(await screen.findByRole("option", { name: "Python" })).toBeInTheDocument()
  expect(screen.queryByRole("option", { name: "Guitarra" })).not.toBeInTheDocument()
})

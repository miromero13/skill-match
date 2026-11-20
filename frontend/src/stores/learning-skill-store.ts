import { create } from "zustand"
import { learningSkillService } from "@/services/learning-skill-service"
import { searchService } from "@/services/search-service"
import type { Category } from "@/types/catalog"
import type {
  UserLearningSkill,
  UserLearningSkillCreate,
  UserLearningSkillUpdate,
  CatalogSkillOption,
} from "@/types/learning-skill"

interface LearningSkillState {
  learningSkills: UserLearningSkill[]
  catalogSkills: CatalogSkillOption[]
  categories: Category[]
  isLoading: boolean
  isCatalogLoading: boolean
  error: string | null

  fetchLearningSkills: () => Promise<void>
  fetchCategories: () => Promise<void>
  fetchCatalogSkills: (search?: string, categoryId?: string) => Promise<void>
  addLearningSkill: (payload: UserLearningSkillCreate) => Promise<boolean>
  updateLearningSkill: (id: string, payload: UserLearningSkillUpdate) => Promise<boolean>
  deleteLearningSkill: (id: string) => Promise<boolean>
}

export const useLearningSkillStore = create<LearningSkillState>((set) => ({
  learningSkills: [],
  catalogSkills: [],
  categories: [],
  isLoading: false,
  isCatalogLoading: false,
  error: null,

  fetchLearningSkills: async () => {
    set({ isLoading: true, error: null })
    try {
      const skills = await learningSkillService.getMyLearningSkills()
      set({ learningSkills: skills, isLoading: false })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error al cargar habilidades deseadas"
      set({ error: msg, isLoading: false })
    }
  },

  fetchCategories: async () => {
    try {
      const categories = await searchService.getCategories()
      set({ categories })
    } catch {
      set({ categories: [] })
    }
  },

  fetchCatalogSkills: async (search?: string, categoryId?: string) => {
    set({ isCatalogLoading: true })
    try {
      const catalog = await learningSkillService.getAvailableCatalogSkills(categoryId, search)
      set({ catalogSkills: catalog, isCatalogLoading: false })
    } catch {
      set({ isCatalogLoading: false })
    }
  },

  addLearningSkill: async (payload: UserLearningSkillCreate) => {
    try {
      const created = await learningSkillService.addLearningSkill(payload)
      set((state) => ({
        learningSkills: [created, ...state.learningSkills],
      }))
      return true
    } catch {
      return false
    }
  },

  updateLearningSkill: async (id: string, payload: UserLearningSkillUpdate) => {
    try {
      const updated = await learningSkillService.updateLearningSkill(id, payload)
      set((state) => ({
        learningSkills: state.learningSkills.map((item) =>
          item.id === id ? updated : item
        ),
      }))
      return true
    } catch {
      return false
    }
  },

  deleteLearningSkill: async (id: string) => {
    try {
      await learningSkillService.deleteLearningSkill(id)
      set((state) => ({
        learningSkills: state.learningSkills.filter((item) => item.id !== id),
      }))
      return true
    } catch {
      return false
    }
  },
}))

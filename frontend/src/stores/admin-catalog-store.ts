import { create } from "zustand"
import type {
  Category,
  ChallengeType,
  Skill,
  CreateCategoryPayload,
  CreateChallengeTypePayload,
  CreateSkillPayload,
  UpdateSkillPayload,
} from "@/types/catalog"
import {
  getCategories,
  createCategory as apiCreateCategory,
  getChallengeTypes,
  createChallengeType as apiCreateChallengeType,
  getSkills,
  getSkill as apiGetSkill,
  createSkill as apiCreateSkill,
  updateSkill as apiUpdateSkill,
  toggleSkillReady as apiToggleSkillReady,
  toggleSkillStatus as apiToggleSkillStatus,
  deleteSkill as apiDeleteSkill,
} from "@/services/admin-catalog-service"

interface AdminCatalogState {
  categories: Category[]
  challengeTypes: ChallengeType[]
  skills: Skill[]
  totalSkills: number
  selectedCategoryId: string | null
  searchTerm: string
  readyFilter: "all" | "ready" | "draft"
  isLoading: boolean
  isSubmitting: boolean
  error: string | null

  // Modals state
  isSkillModalOpen: boolean
  isCategoryModalOpen: boolean
  isChallengeTypeModalOpen: boolean
  editingSkill: Skill | null

  // Actions
  setSelectedCategoryId: (categoryId: string | null) => void
  setSearchTerm: (term: string) => void
  setReadyFilter: (filter: "all" | "ready" | "draft") => void
  clearError: () => void

  openCreateSkillModal: () => void
  openEditSkillModal: (skill: Skill) => void
  closeSkillModal: () => void

  openCategoryModal: () => void
  closeCategoryModal: () => void

  openChallengeTypeModal: () => void
  closeChallengeTypeModal: () => void

  fetchInitialData: () => Promise<void>
  fetchCategories: () => Promise<void>
  fetchChallengeTypes: () => Promise<void>
  fetchSkills: () => Promise<void>

  createCategory: (payload: CreateCategoryPayload) => Promise<Category | null>
  createChallengeType: (payload: CreateChallengeTypePayload) => Promise<ChallengeType | null>
  saveSkill: (payload: CreateSkillPayload | UpdateSkillPayload, skillId?: string) => Promise<boolean>
  toggleReady: (skillId: string, currentReady: boolean) => Promise<boolean>
  toggleStatus: (skillId: string, currentActive: boolean) => Promise<boolean>
  deleteSkill: (skillId: string) => Promise<boolean>
}

export const useAdminCatalogStore = create<AdminCatalogState>((set, get) => ({
  categories: [],
  challengeTypes: [],
  skills: [],
  totalSkills: 0,
  selectedCategoryId: null,
  searchTerm: "",
  readyFilter: "all",
  isLoading: false,
  isSubmitting: false,
  error: null,

  isSkillModalOpen: false,
  isCategoryModalOpen: false,
  isChallengeTypeModalOpen: false,
  editingSkill: null,

  setSelectedCategoryId: (categoryId) => {
    set({ selectedCategoryId: categoryId })
    get().fetchSkills()
  },

  setSearchTerm: (term) => {
    set({ searchTerm: term })
  },

  setReadyFilter: (filter) => {
    set({ readyFilter: filter })
  },

  clearError: () => set({ error: null }),

  openCreateSkillModal: () => set({ isSkillModalOpen: true, editingSkill: null, error: null }),
  openEditSkillModal: async (skill) => {
    set({ isSkillModalOpen: true, editingSkill: skill, error: null })
    try {
      const fullSkill = await apiGetSkill(skill.id)
      set({ editingSkill: fullSkill })
    } catch {
      // Keep existing skill in state if full fetch fails
    }
  },
  closeSkillModal: () => set({ isSkillModalOpen: false, editingSkill: null, error: null }),

  openCategoryModal: () => set({ isCategoryModalOpen: true, error: null }),
  closeCategoryModal: () => set({ isCategoryModalOpen: false, error: null }),

  openChallengeTypeModal: () => set({ isChallengeTypeModalOpen: true, error: null }),
  closeChallengeTypeModal: () => set({ isChallengeTypeModalOpen: false, error: null }),

  fetchInitialData: async () => {
    set({ isLoading: true, error: null })
    try {
      const [cats, challenges, { items, count }] = await Promise.all([
        getCategories(),
        getChallengeTypes(),
        getSkills(get().selectedCategoryId || undefined, get().searchTerm || undefined),
      ])
      set({
        categories: cats,
        challengeTypes: challenges,
        skills: items,
        totalSkills: count,
        isLoading: false,
      })
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error al cargar catálogo"
      set({ error: message, isLoading: false })
    }
  },

  fetchCategories: async () => {
    try {
      const cats = await getCategories()
      set({ categories: cats })
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error al cargar categorías"
      set({ error: message })
    }
  },

  fetchChallengeTypes: async () => {
    try {
      const types = await getChallengeTypes()
      set({ challengeTypes: types })
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error al cargar tipos de desafío"
      set({ error: message })
    }
  },

  fetchSkills: async () => {
    set({ isLoading: true, error: null })
    try {
      const { selectedCategoryId, searchTerm } = get()
      const { items, count } = await getSkills(
        selectedCategoryId || undefined,
        searchTerm ? searchTerm.trim() : undefined
      )
      set({ skills: items, totalSkills: count, isLoading: false })
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error al filtrar habilidades"
      set({ error: message, isLoading: false })
    }
  },

  createCategory: async (payload) => {
    set({ isSubmitting: true, error: null })
    try {
      const newCat = await apiCreateCategory(payload)
      set((state) => ({
        categories: [...state.categories, newCat],
        isCategoryModalOpen: false,
        isSubmitting: false,
      }))
      return newCat
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error al crear categoría"
      set({ error: message, isSubmitting: false })
      return null
    }
  },

  createChallengeType: async (payload) => {
    set({ isSubmitting: true, error: null })
    try {
      const newType = await apiCreateChallengeType(payload)
      set((state) => ({
        challengeTypes: [...state.challengeTypes, newType],
        isChallengeTypeModalOpen: false,
        isSubmitting: false,
      }))
      return newType
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error al crear tipo de desafío"
      set({ error: message, isSubmitting: false })
      return null
    }
  },

  saveSkill: async (payload, skillId) => {
    set({ isSubmitting: true, error: null })
    try {
      if (skillId) {
        const updated = await apiUpdateSkill(skillId, payload as UpdateSkillPayload)
        set((state) => ({
          skills: state.skills.map((s) => (s.id === skillId ? updated : s)),
          isSkillModalOpen: false,
          editingSkill: null,
          isSubmitting: false,
        }))
      } else {
        const created = await apiCreateSkill(payload as CreateSkillPayload)
        set((state) => ({
          skills: [created, ...state.skills],
          totalSkills: state.totalSkills + 1,
          isSkillModalOpen: false,
          editingSkill: null,
          isSubmitting: false,
        }))
      }
      return true
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error al guardar habilidad"
      set({ error: message, isSubmitting: false })
      return false
    }
  },

  toggleReady: async (skillId, currentReady) => {
    try {
      const updated = await apiToggleSkillReady(skillId, !currentReady)
      set((state) => ({
        skills: state.skills.map((s) => (s.id === skillId ? updated : s)),
      }))
      return true
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error al actualizar estado de publicación"
      set({ error: message })
      return false
    }
  },

  toggleStatus: async (skillId, currentActive) => {
    try {
      const updated = await apiToggleSkillStatus(skillId, !currentActive)
      set((state) => ({
        skills: state.skills.map((s) => (s.id === skillId ? updated : s)),
      }))
      return true
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error al actualizar estado"
      set({ error: message })
      return false
    }
  },

  deleteSkill: async (skillId) => {
    try {
      await apiDeleteSkill(skillId)
      set((state) => ({
        skills: state.skills.filter((s) => s.id !== skillId),
        totalSkills: Math.max(0, state.totalSkills - 1),
      }))
      return true
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error al eliminar habilidad"
      set({ error: message })
      return false
    }
  },
}))

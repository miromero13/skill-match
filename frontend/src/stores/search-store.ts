import { create } from "zustand"
import { searchService } from "@/services/search-service"
import type { Category, Skill } from "@/types/catalog"
import type { TutorSearchFilters, TutorSearchResult } from "@/types/search"

interface TutorSearchState {
  filters: TutorSearchFilters
  tutors: TutorSearchResult[]
  totalCount: number
  isLoading: boolean
  error: string | null
  apiMessage: string
  categories: Category[]
  skills: Skill[]

  setFilter: <K extends keyof TutorSearchFilters>(
    key: K,
    value: TutorSearchFilters[K]
  ) => void
  setFilters: (partial: Partial<TutorSearchFilters>) => void
  resetFilters: () => void
  fetchTutors: () => Promise<void>
  fetchCatalogData: () => Promise<void>
}

const defaultFilters: TutorSearchFilters = {
  query: "",
  category_id: "",
  skill_id: "",
  min_level: "",
  verified_only: false,
  modality: undefined,
  max_distance: undefined,
  sort_by: "reputation",
  page: 1,
  page_size: 12,
}

export const useTutorSearchStore = create<TutorSearchState>((set, get) => ({
  filters: { ...defaultFilters },
  tutors: [],
  totalCount: 0,
  isLoading: false,
  error: null,
  apiMessage: "",
  categories: [],
  skills: [],

  setFilter: (key, value) => {
    set((state) => ({
      filters: {
        ...state.filters,
        [key]: value,
        // Reset page a 1 cuando cambie cualquier filtro que no sea page
        page: key === "page" ? (value as number) : 1,
      },
    }))
    get().fetchTutors()
  },

  setFilters: (partial) => {
    set((state) => ({
      filters: {
        ...state.filters,
        ...partial,
        page: partial.page ?? 1,
      },
    }))
    get().fetchTutors()
  },

  resetFilters: () => {
    set({ filters: { ...defaultFilters } })
    get().fetchTutors()
  },

  fetchTutors: async () => {
    set({ isLoading: true, error: null })
    try {
      const response = await searchService.searchTutors(get().filters)
      set({
        tutors: response.data || [],
        totalCount: response.count ?? (response.data ? response.data.length : 0),
        apiMessage: response.message || "Búsqueda completada",
        isLoading: false,
      })
    } catch (err: unknown) {
      const errorMsg =
        err instanceof Error ? err.message : "Error al buscar instructores"
      set({ error: errorMsg, isLoading: false })
    }
  },

  fetchCatalogData: async () => {
    try {
      const [categories, skills] = await Promise.all([
        searchService.getCategories(),
        searchService.getSkills(),
      ])
      set({ categories, skills })
    } catch {
      // Ignorar errores en carga de metadatos no críticos
    }
  },
}))

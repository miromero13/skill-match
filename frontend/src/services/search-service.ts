import { apiClient } from "@/services/api-client"
import type { APIResponse } from "@/types/api"
import type { Category, Skill } from "@/types/catalog"
import type { TutorSearchFilters, TutorSearchResult } from "@/types/search"

export const searchService = {
  /**
   * Búsqueda facetada de instructores con filtros multidimensionales (HU-20 / RF-MAT-01, RF-MAT-02, RF-MAT-11)
   */
  async searchTutors(filters: TutorSearchFilters): Promise<APIResponse<TutorSearchResult[]>> {
    const params: Record<string, string | number | boolean | undefined> = {}

    if (filters.query?.trim()) params.query = filters.query.trim()
    if (filters.skill_id) params.skill_id = filters.skill_id
    if (filters.category_id) params.category_id = filters.category_id
    if (filters.min_level) params.min_level = filters.min_level
    if (filters.verified_only) params.verified_only = true
    if (filters.modality) params.modality = filters.modality
    if (filters.max_distance !== undefined && filters.max_distance > 0) {
      params.max_distance = filters.max_distance
    }
    if (filters.latitude !== undefined) params.latitude = filters.latitude
    if (filters.longitude !== undefined) params.longitude = filters.longitude
    if (filters.sort_by) params.sort_by = filters.sort_by
    if (filters.page) params.page = filters.page
    if (filters.page_size) params.page_size = filters.page_size

    return apiClient.get<TutorSearchResult[]>("/search/tutors", {
      params,
      showToastOnError: true,
    })
  },

  /**
   * Obtiene las categorías del catálogo para poblar el selector de filtros
   */
  async getCategories(): Promise<Category[]> {
    const res = await apiClient.get<Category[]>("/categories", {
      showToastOnError: false,
    })
    return res.data || []
  },

  /**
   * Obtiene las habilidades del catálogo opcionalmente filtradas por categoría
   */
  async getSkills(categoryId?: string): Promise<Skill[]> {
    const params: Record<string, string | number | boolean | undefined> = {}
    if (categoryId) params.category_id = categoryId

    const res = await apiClient.get<Skill[]>("/skills", {
      params,
      showToastOnError: false,
    })
    return res.data || []
  },
}

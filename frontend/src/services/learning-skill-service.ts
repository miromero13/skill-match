import { apiClient } from "@/services/api-client"
import type {
  UserLearningSkill,
  UserLearningSkillCreate,
  UserLearningSkillUpdate,
  CatalogSkillOption,
} from "@/types/learning-skill"

export const learningSkillService = {
  /**
   * Obtiene la lista de habilidades que el usuario actual desea aprender (HU-15)
   */
  async getMyLearningSkills(): Promise<UserLearningSkill[]> {
    const res = await apiClient.get<UserLearningSkill[]>("/users/me/learning-skills", {
      showToastOnError: true,
    })
    return res.data || []
  },

  /**
   * Agrega una nueva habilidad a la lista de aprendizaje del usuario
   */
  async addLearningSkill(payload: UserLearningSkillCreate): Promise<UserLearningSkill> {
    const res = await apiClient.post<UserLearningSkill>("/users/me/learning-skills", payload, {
      showToastOnError: true,
      showToastOnSuccess: true,
      successMessage: "¡Habilidad agregada a tu lista de aprendizaje!",
    })
    return res.data
  },

  /**
   * Actualiza el nivel actual, objetivo o urgencia de una habilidad deseada
   */
  async updateLearningSkill(
    id: string,
    payload: UserLearningSkillUpdate
  ): Promise<UserLearningSkill> {
    const res = await apiClient.put<UserLearningSkill>(`/users/me/learning-skills/${id}`, payload, {
      showToastOnError: true,
      showToastOnSuccess: true,
      successMessage: "Habilidad actualizada correctamente",
    })
    return res.data
  },

  /**
   * Elimina una habilidad de la lista de aprendizaje
   */
  async deleteLearningSkill(id: string): Promise<void> {
    await apiClient.delete<void>(`/users/me/learning-skills/${id}`, {
      showToastOnError: true,
      showToastOnSuccess: true,
      successMessage: "Habilidad removida de tu lista",
    })
  },

  /**
   * Obtiene las habilidades disponibles en el catálogo para selección
   */
  async getAvailableCatalogSkills(
    categoryId?: string,
    search?: string
  ): Promise<CatalogSkillOption[]> {
    const params: Record<string, string> = {}
    if (categoryId) params.category_id = categoryId
    if (search) params.search = search

    const res = await apiClient.get<CatalogSkillOption[]>("/skills", {
      params,
      showToastOnError: false,
    })
    return res.data || []
  },
}

import { apiClient } from "@/services/api-client"
import type {
  Category,
  ChallengeType,
  Skill,
  CreateCategoryPayload,
  UpdateCategoryPayload,
  CreateChallengeTypePayload,
  CreateSkillPayload,
  UpdateSkillPayload,
} from "@/types/catalog"

/** Categorías */
export async function getCategories(): Promise<Category[]> {
  const response = await apiClient.get<Category[]>("/admin/catalog/categories", {
    showToastOnError: true,
  })
  return response.data || []
}

export async function createCategory(payload: CreateCategoryPayload): Promise<Category> {
  const response = await apiClient.post<Category>("/admin/catalog/categories", payload, {
    showToastOnError: true,
    showToastOnSuccess: true,
  })
  return response.data
}

export async function updateCategory(id: string, payload: UpdateCategoryPayload): Promise<Category> {
  const response = await apiClient.put<Category>(`/admin/catalog/categories/${id}`, payload, {
    showToastOnError: true,
    showToastOnSuccess: true,
  })
  return response.data
}

export async function deleteCategory(id: string): Promise<void> {
  await apiClient.delete<null>(`/admin/catalog/categories/${id}`, {
    showToastOnError: true,
    showToastOnSuccess: true,
  })
}

/** Tipos de Desafío IA */
export async function getChallengeTypes(): Promise<ChallengeType[]> {
  const response = await apiClient.get<ChallengeType[]>("/admin/catalog/challenge-types", {
    showToastOnError: true,
  })
  return response.data || []
}

export async function createChallengeType(payload: CreateChallengeTypePayload): Promise<ChallengeType> {
  const response = await apiClient.post<ChallengeType>("/admin/catalog/challenge-types", payload, {
    showToastOnError: true,
    showToastOnSuccess: true,
  })
  return response.data
}

/** Habilidades */
export async function getSkills(categoryId?: string, search?: string): Promise<{ items: Skill[]; count: number }> {
  const params = new URLSearchParams()
  if (categoryId) params.append("category_id", categoryId)
  if (search) params.append("search", search)

  const url = `/admin/catalog/skills${params.toString() ? `?${params.toString()}` : ""}`
  const response = await apiClient.get<Skill[]>(url, {
    showToastOnError: true,
  })
  return {
    items: response.data || [],
    count: response.count ?? (response.data ? response.data.length : 0),
  }
}

export async function getSkill(id: string): Promise<Skill> {
  const response = await apiClient.get<Skill>(`/admin/catalog/skills/${id}`, {
    showToastOnError: true,
  })
  return response.data
}

export async function createSkill(payload: CreateSkillPayload): Promise<Skill> {
  const response = await apiClient.post<Skill>("/admin/catalog/skills", payload, {
    showToastOnError: true,
    showToastOnSuccess: true,
  })
  return response.data
}

export async function updateSkill(id: string, payload: UpdateSkillPayload): Promise<Skill> {
  const response = await apiClient.put<Skill>(`/admin/catalog/skills/${id}`, payload, {
    showToastOnError: true,
    showToastOnSuccess: true,
  })
  return response.data
}

export async function toggleSkillReady(id: string, is_ready_to_publish: boolean): Promise<Skill> {
  const response = await apiClient.patch<Skill>(
    `/admin/catalog/skills/${id}/ready`,
    { is_ready_to_publish },
    {
      showToastOnError: true,
      showToastOnSuccess: true,
    }
  )
  return response.data
}

export async function toggleSkillStatus(id: string, is_active: boolean): Promise<Skill> {
  const response = await apiClient.patch<Skill>(
    `/admin/catalog/skills/${id}/status`,
    { is_active },
    {
      showToastOnError: true,
      showToastOnSuccess: true,
    }
  )
  return response.data
}

export async function deleteSkill(id: string): Promise<void> {
  await apiClient.delete<null>(`/admin/catalog/skills/${id}`, {
    showToastOnError: true,
    showToastOnSuccess: true,
  })
}

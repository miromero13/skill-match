import { apiClient } from "@/services/api-client"
import type {
    AvailableSkill,
    TeachingSkill,
    TeachingSkillPayload,
} from "@/types/teaching-skills"

const endpoint = "/users/me/teaching-skills"
const mutationOptions = {
    showToastOnError: true,
    showToastOnSuccess: true,
}

export async function getTeachingCatalog() {
    const response = await apiClient.get<AvailableSkill[]>(
        `${endpoint}/catalog`,
        { showToastOnError: true },
    )
    return response.data
}

export async function getTeachingSkills(page: number) {
    return apiClient.get<TeachingSkill[]>(
        `${endpoint}?page=${page}&page_size=20`,
        { showToastOnError: true },
    )
}

export async function saveTeachingSkill(
    payload: TeachingSkillPayload,
    id?: string,
) {
    if (id) {
        return apiClient.put<TeachingSkill>(
            `${endpoint}/${id}`, payload, mutationOptions,
        )
    }

    return apiClient.post<TeachingSkill>(
        endpoint, payload, mutationOptions,
    )
}

export async function deleteTeachingSkill(id: string) {
    await apiClient.delete<null>(
        `${endpoint}/${id}`, mutationOptions,
    )
}
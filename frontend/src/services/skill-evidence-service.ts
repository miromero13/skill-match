import { apiClient } from "@/services/api-client"
import type { EvidencePayload, SkillEvidence } from "@/types/skill-evidence"

const endpoint = (skillId: string) =>
  `/users/me/teaching-skills/${encodeURIComponent(skillId)}/evidences`
const mutations = { showToastOnError: true, showToastOnSuccess: true }

export function getEvidences(skillId: string, page = 1) {
  return apiClient.get<SkillEvidence[]>(endpoint(skillId), {
    params: { page, page_size: 20 },
    showToastOnError: false,
  })
}
export function createEvidence(skillId: string, payload: EvidencePayload) {
  return apiClient.post<SkillEvidence>(endpoint(skillId), payload, mutations)
}
export function updateEvidence(
  skillId: string,
  evidenceId: string,
  payload: EvidencePayload
) {
  return apiClient.put<SkillEvidence>(
    `${endpoint(skillId)}/${encodeURIComponent(evidenceId)}`,
    payload,
    mutations
  )
}
export function deleteEvidence(skillId: string, evidenceId: string) {
  return apiClient.delete<null>(
    `${endpoint(skillId)}/${encodeURIComponent(evidenceId)}`,
    mutations
  )
}

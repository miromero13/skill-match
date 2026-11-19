import { apiClient } from "@/services/api-client"
import type { ProgrammingChallenge, ProgrammingChallengePayload, ProgrammingRunResult, ProgrammingSubmissionResult } from "@/types/programming"

export async function listProgrammingChallenges(skillId?: string): Promise<ProgrammingChallenge[]> {
  const response = await apiClient.get<ProgrammingChallenge[]>("/admin/programming/challenges", {
    params: skillId ? { skill_id: skillId } : undefined,
    showToastOnError: true,
  })
  return response.data || []
}

export async function createProgrammingChallenge(payload: ProgrammingChallengePayload): Promise<ProgrammingChallenge> {
  const response = await apiClient.post<ProgrammingChallenge>("/admin/programming/challenges", payload, {
    showToastOnError: true,
    showToastOnSuccess: true,
  })
  return response.data
}

export async function getEvaluationProgrammingChallenge(evaluationId: string): Promise<ProgrammingChallenge> {
  const response = await apiClient.get<ProgrammingChallenge>(`/programming/evaluations/${evaluationId}/challenge`, {
    showToastOnError: true,
  })
  return response.data
}

export async function runProgrammingChallenge(challengeId: string, code: string): Promise<ProgrammingRunResult> {
  const response = await apiClient.post<ProgrammingRunResult>(`/programming/challenges/${challengeId}/run`, { code }, {
    showToastOnError: true,
    showToastOnSuccess: false,
  })
  return response.data
}

export async function submitProgrammingSolution(evaluationId: string, challengeId: string, code: string): Promise<ProgrammingSubmissionResult> {
  const response = await apiClient.post<ProgrammingSubmissionResult>(`/programming/evaluations/${evaluationId}/challenges/${challengeId}/submit`, { code }, {
    showToastOnError: true,
    showToastOnSuccess: true,
  })
  return response.data
}

export async function publishProgrammingChallenge(id: string): Promise<ProgrammingChallenge> {
  const response = await apiClient.post<ProgrammingChallenge>(`/admin/programming/challenges/${id}/publish`, {}, {
    showToastOnError: true,
    showToastOnSuccess: true,
  })
  return response.data
}

import { apiClient } from "@/services/api-client"
import type { Challenge, ChallengePayload, ChallengeRunResult, ChallengeSubmissionResult } from "@/types/programming"

export async function listChallenges(skillId?: string): Promise<Challenge[]> {
  const response = await apiClient.get<Challenge[]>("/admin/challenges", {
    params: skillId ? { skill_id: skillId } : undefined,
    showToastOnError: true,
  })
  return response.data || []
}

export async function createChallenge(payload: ChallengePayload): Promise<Challenge> {
  const response = await apiClient.post<Challenge>("/admin/challenges", payload, {
    showToastOnError: true,
    showToastOnSuccess: true,
  })
  return response.data
}

export async function getEvaluationChallenge(evaluationId: string): Promise<Challenge> {
  const response = await apiClient.get<Challenge>(`/challenges/evaluations/${evaluationId}/challenge`, {
    showToastOnError: true,
  })
  return response.data
}

export async function runChallenge(challengeId: string, code: string): Promise<ChallengeRunResult> {
  const response = await apiClient.post<ChallengeRunResult>(`/challenges/${challengeId}/run`, { code }, {
    showToastOnError: true,
    showToastOnSuccess: false,
  })
  return response.data
}

export async function submitChallengeSolution(evaluationId: string, challengeId: string, code: string): Promise<ChallengeSubmissionResult> {
  const response = await apiClient.post<ChallengeSubmissionResult>(`/challenges/evaluations/${evaluationId}/challenges/${challengeId}/submit`, { code }, {
    showToastOnError: true,
    showToastOnSuccess: true,
  })
  return response.data
}

export async function publishChallenge(id: string): Promise<Challenge> {
  const response = await apiClient.post<Challenge>(`/admin/challenges/${id}/publish`, {}, {
    showToastOnError: true,
    showToastOnSuccess: true,
  })
  return response.data
}

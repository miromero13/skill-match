import { apiClient } from "@/services/api-client"

export interface EvaluationPreflight {
  teaching_skill_id: string
  skill_name: string
  syllabus: string
  requirements: string[]
  stages: string[]
  estimated_duration_minutes: number | null
  free_evaluations_left: number
  attempts_used: number
  policy_version: string
  pending_evaluation_id: string | null
}

export interface EvaluationConsent {
  id: string
  status: string
  biometric_consent_at: string
  policy_version: string
  started_at: string | null
}

export interface ConsentPayload {
  biometric_consent: true
  integrity_consent: true
  attempt_rule_accepted: true
  policy_version: string
}

export interface CalibrationChallenge {
  id: string
  action: "TURN_LEFT" | "TURN_RIGHT"
  expires_at: string
}

export interface CalibrationState {
  evaluation_id: string
  ready: boolean
  status: string
  started_at: string | null
  checks: Record<string, boolean>
}

export interface CalibrationEvidence {
  challenge_id: string
  frames: string[]
  audio_samples: number[]
  camera_label: string
}

export async function requestCalibrationChallenge(id: string) {
  return (await apiClient.post<CalibrationChallenge>(
    `/evaluations/${encodeURIComponent(id)}/liveness/challenge`, {},
  )).data
}

export async function verifyEvaluationCalibration(id: string, evidence: CalibrationEvidence) {
  return (await apiClient.post<CalibrationState>(
    `/evaluations/${encodeURIComponent(id)}/liveness/verify-identity`, evidence,
    { showToastOnError: true, showToastOnSuccess: true },
  )).data
}

export async function getEvaluationPreflight(id: string) {
  return (await apiClient.get<EvaluationPreflight>(
    `/evaluations/skills/${encodeURIComponent(id)}/preflight`,
  )).data
}

export async function registerEvaluationConsent(id: string, payload: ConsentPayload) {
  return (await apiClient.post<EvaluationConsent>(
    `/evaluations/skills/${encodeURIComponent(id)}/consent`, payload,
    { showToastOnError: true, showToastOnSuccess: true },
  )).data
}

import { apiClient } from "@/services/api-client"
import type { GazeCalibrationPoint } from "@/services/browser-supervision"
import type { MouthSampleDTO } from "@/services/gaze-tracking"

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

/** Body of `POST /evaluations/{id}/liveness/verify-identity`; the server rejects extra fields and any missing one. */
export interface CalibrationEvidence {
  challenge_id: string
  /** 3 to 12 JPEGs of the head movement. */
  frames: string[]
  /** Exactly one point per target (CENTER and the four corners), 1 to 6 JPEGs each. */
  gaze_points: GazeCalibrationPoint[]
  /** 16 kHz silence (32000 to 64000 samples). */
  ambient_audio_samples: number[]
  /** 16 kHz phrase then pause (112000 to 160000 samples); nothing may be said from 4.5 s on. */
  audio_samples: number[]
  /** 20 to 100 JPEGs, `time_ms` counted from the start of `audio_samples`. */
  spoken_frames: { time_ms: number; image: string }[]
  /** 8 to 450 mouth readings, `t_ms` counted from the start of `audio_samples`. */
  mouth_samples: MouthSampleDTO[]
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

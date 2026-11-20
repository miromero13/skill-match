import { apiClient } from "@/services/api-client"

export interface PublicTheoryQuestion {
  id: string
  version: number
  position: number
  kind: string
  prompt: string
  choices: { code: string; text: string }[]
  time_limit_seconds: number
  max_score: number
}
export interface TheoryProgress {
  evaluation_id: string
  status: string
  question_count: number
  answered_count: number
  position: number
  server_time: string
  deadline_at: string
  question_deadline_at: string | null
  current_question: PublicTheoryQuestion | null
  grading_state: string
  grading_score: number | null
  grading_feedback: { question_id: string; points: number; max_score: number; feedback: string; criteria: { name: string; weight: number; attainment: number; reason: string }[] }[] | null
  has_coding_stage?: boolean
}
export interface FinalEvaluationResult {
  evaluation_id: string
  status: string
  passed: boolean
  final_score: number
  theory_score: number
  theory_max_score: number
  theory_feedback: { question_id: string; points: number; max_score: number; feedback: string; criteria: { name: string; weight: number; attainment: number; reason: string }[] }[] | null
  has_coding_stage: boolean
  sandbox_passed_tests: number | null
  sandbox_total_tests: number | null
  defense_transcript: string | null
  defense_score: number | null
  defense_feedback: string | null
  skill_validated: boolean
}
export interface OralSubmission { submission_id: string; question_id: string; audio_base64: string }
export const theoryExam = {
  status: (id: string) => apiClient.get<TheoryProgress>(`/evaluations/${id}/status`, { showToastOnError: false }),
  answer: (id: string, payload: OralSubmission) => apiClient.post<{ transcript: string }>(`/evaluations/${id}/answers`, payload, { showToastOnError: false }),
  result: (id: string) => apiClient.get(`/evaluations/${id}/result`, { showToastOnError: false }),
  retryGrading: (id: string) => apiClient.post(`/evaluations/${id}/grading/retry`, {}, { showToastOnError: false }),
  finalize: (id: string) => apiClient.post<FinalEvaluationResult>(`/evaluations/${id}/finalize`, {}, { showToastOnError: false }),
  start: (id: string, level_number: number, text_grading_consent: boolean) => apiClient.post(`/evaluations/start`, { evaluation_id: id, level_number, text_grading_consent }, { showToastOnError: false }),
  cancel: (id: string) => apiClient.post<{ evaluation_id: string; status: string }>(`/evaluations/${id}/cancel`, {}, { showToastOnError: false }),
}

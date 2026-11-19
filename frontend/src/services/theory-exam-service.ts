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
}
export interface OralSubmission { submission_id: string; question_id: string; audio_base64: string }
export const theoryExam = {
  status: (id: string) => apiClient.get<TheoryProgress>(`/evaluations/${id}/status`, { showToastOnError: false }),
  start: (id: string, level_number: number) => apiClient.post(`/evaluations/start`, { evaluation_id: id, level_number }, { showToastOnError: false }),
  answer: (id: string, payload: OralSubmission) => apiClient.post<{ transcript: string }>(`/evaluations/${id}/answers`, payload, { showToastOnError: false }),
}

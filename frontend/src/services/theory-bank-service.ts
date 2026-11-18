import { apiClient } from "@/services/api-client"

export interface QuestionContent {
  kind: "OPEN" | "MULTIPLE_CHOICE" | "TRUE_FALSE"
  prompt: string
  choices: { code: string; text: string }[]
  correct_choice: string | null
  reference_answer: string
  criteria: { name: string; weight: number; description: string }[]
  time_limit_seconds: number
  max_score: number
}
export interface TheoryQuestion {
  id: string
  version: number
  skill_id: string
  level_number: number
  status: "DRAFT" | "PUBLISHED" | "ARCHIVED"
  content: QuestionContent
}
const root = "/admin/theory/questions"
export const theoryBank = {
  list: (params: Record<string, string | number | undefined>) => apiClient.get<TheoryQuestion[]>(root, { params }),
  create: (payload: QuestionContent & { skill_id: string; level_number: number }) => apiClient.post<TheoryQuestion>(root, payload),
  edit: (id: string, expected_version: number, content: QuestionContent) => apiClient.patch<TheoryQuestion>(`${root}/${id}`, { expected_version, content }),
  publish: (id: string, expected_version: number) => apiClient.post<TheoryQuestion>(`${root}/${id}/publish`, { expected_version }),
  archive: (id: string, expected_version: number) => apiClient.post<TheoryQuestion>(`${root}/${id}/archive`, { expected_version }),
  history: (id: string) => apiClient.get<TheoryQuestion[]>(`${root}/${id}/versions`),
}

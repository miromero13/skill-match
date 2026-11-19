export type ChallengeVisibility = "PUBLIC" | "HIDDEN"
export type ChallengeStatus = "DRAFT" | "PUBLISHED" | "ARCHIVED"
export type EvaluationModality = "SANDBOX" | "SPREADSHEET"

export interface ChallengeTestCase {
  name: string
  stdin_data: string
  expected_stdout: string
  visibility: ChallengeVisibility
  order_index: number
}

export interface Challenge {
  id: string
  skill_id: string
  level_number: number
  version: number
  title: string
  statement: string
  evaluation_modality: EvaluationModality
  execution_profile: string
  starter_code: string
  time_limit_ms: number
  memory_limit_mb: number
  max_output_bytes: number
  allowed_imports: string[]
  tests: ChallengeTestCase[]
  status: ChallengeStatus
  published_at: string | null
}

export interface ChallengeTestResult {
  name: string
  passed: boolean
  stdout: string
  stderr: string
  exit_code: number | null
  timed_out: boolean
}

export interface ChallengeRunResult {
  challenge_id: string
  passed_tests: number
  total_tests: number
  status: "PASSED" | "FAILED" | "REJECTED" | "ERROR"
  results: ChallengeTestResult[]
}

export interface ChallengeSubmissionResult extends ChallengeRunResult {
  submission_id: string
  submitted_at: string
}

export interface ChallengePayload {
  skill_id: string
  level_number: number
  title: string
  statement: string
  evaluation_modality: EvaluationModality
  execution_profile: string
  starter_code: string
  time_limit_ms: number
  memory_limit_mb: number
  max_output_bytes: number
  allowed_imports: string[]
  blocked_imports: string[]
  tests: ChallengeTestCase[]
}

export type ProgrammingVisibility = "PUBLIC" | "HIDDEN"
export type ProgrammingStatus = "DRAFT" | "PUBLISHED" | "ARCHIVED"

export interface ProgrammingTestCase {
  name: string
  stdin_data: string
  expected_stdout: string
  visibility: ProgrammingVisibility
  order_index: number
}

export interface ProgrammingChallenge {
  id: string
  skill_id: string
  level_number: number
  version: number
  title: string
  statement: string
  language: "python"
  starter_code: string
  time_limit_ms: number
  memory_limit_mb: number
  max_output_bytes: number
  allowed_imports: string[]
  tests: ProgrammingTestCase[]
  status: ProgrammingStatus
  published_at: string | null
}

export interface ProgrammingTestResult {
  name: string
  passed: boolean
  stdout: string
  stderr: string
  exit_code: number | null
  timed_out: boolean
}

export interface ProgrammingRunResult {
  challenge_id: string
  passed_tests: number
  total_tests: number
  status: "PASSED" | "FAILED" | "REJECTED" | "ERROR"
  results: ProgrammingTestResult[]
}

export interface ProgrammingSubmissionResult extends ProgrammingRunResult {
  submission_id: string
  submitted_at: string
}

export interface ProgrammingChallengePayload {
  skill_id: string
  level_number: number
  title: string
  statement: string
  language: "python"
  starter_code: string
  time_limit_ms: number
  memory_limit_mb: number
  max_output_bytes: number
  allowed_imports: string[]
  blocked_imports: string[]
  tests: ProgrammingTestCase[]
}

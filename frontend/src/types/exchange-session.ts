export const exchangeSessionModalities = ["VIRTUAL", "PRESENCIAL"] as const
export const exchangeSessionStatuses = [
  "PENDING",
  "ACCEPTED",
  "REJECTED",
  "CANCELLED",
  "COMPLETED",
] as const

export type ExchangeSessionModality = (typeof exchangeSessionModalities)[number]
export type ExchangeSessionStatus = (typeof exchangeSessionStatuses)[number]

export interface ExchangeSession {
  id: string
  match_id: string
  teaching_skill_id: string
  created_by_id: string
  instructor_id: string
  learner_id: string
  starts_at: string
  ends_at: string
  timezone: string
  modality: ExchangeSessionModality
  status: ExchangeSessionStatus
  is_free: boolean
  cancellation_reason: string | null
  cancelled_by_id: string | null
  cancelled_at: string | null
  quota_restored: boolean
  booking_blocked_until: string | null
  actual_minutes?: number | null
  completed_at?: string | null
  can_confirm?: boolean
  can_report_noshow?: boolean
  my_confirmation?: boolean
  counterpart_confirmation?: boolean
}

export interface SessionConfirmRequest {
  request_key: string
  actual_minutes: number
  topics?: string[]
  presence_pin?: string
}

export interface SessionConfirmResponse {
  session_id: string
  status: ExchangeSessionStatus
  my_confirmation: boolean
  counterpart_confirmation: boolean
  actual_minutes: number | null
  completed_at: string | null
  escrow_release: "NOT_APPLICABLE" | "PENDING_HU42" | "RELEASED"
}

export interface SessionNoShowRequest {
  request_key: string
  reason: string
}

export interface SessionNoShowResponse {
  session_id: string
  reported_by_id: string
  absent_user_id: string
  reason: string
  status: "PENDING_REPUTATION" | "PROCESSED" | "DISMISSED"
  reported_at: string
}

export interface SessionPresencePinResponse {
  session_id: string
  presence_pin: string
  expires_at: string
  attempt_count: number
  is_locked: boolean
}

export interface ExchangeSessionCreate {
  match_id: string
  teaching_skill_id: string
  instructor_id: string
  starts_at: string
  ends_at: string
  timezone: string
  modality: ExchangeSessionModality
}

export interface ExchangeSessionReschedule {
  starts_at: string
  ends_at: string
}

export interface SessionListData {
  items: ExchangeSession[]
  free_sessions_left: number
  free_sessions_limit: number
}

export interface SessionCalendarExport {
  filename: string
  content_type: "text/calendar; charset=utf-8"
  ics_content: string
  google_calendar_url: string
}

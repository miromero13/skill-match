export const exchangeSessionModalities = ["VIRTUAL", "PRESENCIAL"] as const
export const exchangeSessionStatuses = [
  "PENDING",
  "ACCEPTED",
  "REJECTED",
  "CANCELLED",
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

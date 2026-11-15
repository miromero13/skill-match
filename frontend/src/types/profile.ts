export type ExchangeModality = "VIRTUAL" | "PRESENCIAL" | "BOTH"

export interface UserProfileLinks {
  github?: string
  linkedin?: string
  portfolio?: string
  website?: string
  [key: string]: string | undefined
}

export interface UserProfileData {
  id: string
  user_id: string
  full_name: string
  email: string
  bio: string | null
  avatar_url: string | null
  languages: string[]
  timezone: string
  links: Record<string, string>
  exchange_modality: ExchangeModality
  presencial_radius_km: number
  location_label: string | null
  buffer_minutes: number
  gcal_synced: boolean
  gcal_calendar_email: string | null
  has_biometric_enrollment: boolean
  biometric_enrolled_at: string | null
  biometric_face_hash: string | null
  embedding_dimensions?: number | null
}

export interface UserProfileUpdatePayload {
  full_name?: string
  bio?: string | null
  avatar_url?: string | null
  languages: string[]
  timezone: string
  links: Record<string, string>
  exchange_modality: ExchangeModality
  presencial_radius_km: number
  location_label?: string | null
  buffer_minutes: number
  gcal_synced: boolean
  gcal_calendar_email?: string | null
}

export type UserProfilePatchPayload = Partial<UserProfileUpdatePayload>

export interface BiometricEnrollPayload {
  image_base64?: string
  frames?: string[]
  lighting_score: number
  face_centered: boolean
}

export interface AvailabilitySlot {
  id: string
  user_id: string
  day_of_week: number
  start_time: string
  end_time: string
  is_enabled: boolean
  modality: ExchangeModality
}

export interface AvailabilitySlotInput {
  day_of_week: number
  start_time: string
  end_time: string
  is_enabled: boolean
  modality: ExchangeModality
}

export interface AvailabilityMatrixPayload {
  slots: AvailabilitySlotInput[]
  timezone?: string
  buffer_minutes?: number
}

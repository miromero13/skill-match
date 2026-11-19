import type { RatingsBreakdown, ReputationBadge, TrustScoreFactors } from "./reputation"

export interface PassportSkillItem {
  id: string
  name: string
  category_name: string
  declared_level: string
  status: "DECLARADA" | "EN_EVALUACION" | "VERIFICADA"
  years_of_experience: number
  verified_at?: string | null
}

export interface DockerTestCase {
  name: string
  status: string
  duration_seconds: number
  percentage: number
}

export interface DockerSuiteReport {
  passed_count: number
  total_count: number
  execution_time_seconds: number
  coverage_percentage: number
  test_cases: DockerTestCase[]
}

export interface AuditedCodeChallenge {
  title: string
  consigna: string
  file_name: string
  language: string
  source_code: string
  docker_report: DockerSuiteReport
}

export interface OralDefenseAudit {
  score: number
  question: string
  candidate_transcript: string
  ai_verdict: string
}

export interface AntiFraudAudit {
  facial_liveness_score: number
  voice_verification_status: string
  screen_violations_count: number
  clipboard_abuse_detected: boolean
}

export interface TechnicalDossier {
  has_technical_audit: boolean
  evaluated_skill_name?: string | null
  technical_score?: number | null
  oral_defense_score?: number | null
  code_challenge?: AuditedCodeChallenge | null
  oral_defense?: OralDefenseAudit | null
  anti_fraud?: AntiFraudAudit | null
}

export interface PublicPassport {
  public_uuid: string
  certificate_id: string
  full_name: string
  avatar_url?: string | null
  bio?: string | null
  location_label?: string | null
  member_since: string
  issued_at: string
  verification_hash: string
  verification_node: string
  qr_endpoint_url: string
  pdf_download_url: string
  public_shareable_url: string

  // Reputación y Confianza (HU-40)
  trust_score: number
  overall_rating: number
  total_reviews: number
  ratings_breakdown: RatingsBreakdown
  factors: TrustScoreFactors
  badges: ReputationBadge[]

  // Habilidades
  skills: PassportSkillItem[]

  // Dossier Técnico
  technical_dossier: TechnicalDossier
}

export interface MyPassportSummary {
  public_uuid: string
  shareable_url: string
  qr_endpoint_url: string
  pdf_download_url: string
}

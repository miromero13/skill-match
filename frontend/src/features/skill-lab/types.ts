import type { MetricTypeCode } from "@/types/catalog"

/** Contratos de `/api/admin/skill-lab` (odd/tasks/skill-validation-engine.md, "API contract"). */

export type SampleRole = "TRAINING" | "REFERENCE"

export interface SkillLabSample {
  id: string
  skill_id: string
  skill_level_id: string | null
  criterion_key: string | null
  sample_role: SampleRole
  file_format: string
  file_size_bytes: number
  participant_id: string | null
  analysis_ready: boolean
  analysis_notes: string[]
  created_at: string
}

export interface SkillLabModelMetrics {
  samples_per_level?: Record<string, number>
  loo_level_accuracy?: number | null
  notes?: string[]
  [metric: string]: unknown
}

export interface SkillLabModel {
  id: string
  skill_id: string
  version: string
  activa: boolean
  metricas: SkillLabModelMetrics
  created_at: string
}

export interface SkillLabCriterion {
  key: string
  name: string
  weight: number
  description: string
  metric_type: MetricTypeCode
  target: number | null
  training_samples: number
  has_reference: boolean
}

export interface SkillLabLevel {
  id: string
  level_number: number
  name: string
  min_score: number
  weights_total: number
  criteria: SkillLabCriterion[]
  training_samples: number
  reference: SkillLabSample | null
}

export interface SkillLabChallengeType {
  id: string
  name: string
  code: string
  evaluation_modality: string
}

export interface SkillLabSkill {
  id: string
  name: string
  category: { id: string; name: string }
  challenge_type: SkillLabChallengeType | null
  min_approval_threshold: number
}

export interface SkillLabReadiness {
  ready_to_validate: boolean
  issues: string[]
}

export interface SkillLabConfig {
  skill: SkillLabSkill
  levels: SkillLabLevel[]
  active_model: SkillLabModel | null
  readiness: SkillLabReadiness
}

export interface ValidationCriterionResult {
  key: string
  name: string
  weight: number
  metric_type: MetricTypeCode
  evaluable: boolean
  score: number | null
  detail: Record<string, unknown>
  note: string | null
}

export interface ValidationLevelResult {
  level_id: string
  level_number: number
  name: string
  min_score: number
  evaluable: boolean
  score: number | null
  passed: boolean
  not_evaluable_reason: string | null
  criteria: ValidationCriterionResult[]
}

export interface ValidationLevelRef {
  level_id: string
  level_number: number
  name: string
}

export interface ModelLevelEstimate {
  level_id: string
  name: string
  confidence: number
}

/** `data` de `POST /api/admin/skill-lab/skills/{skill_id}/validate` (siempre HTTP 200). */
export interface SkillValidationResult {
  skill_id: string
  skill_name: string
  engine_version: string
  model_version: string | null
  analysis_complete: boolean
  target_level_id: string | null
  achieved_level: ValidationLevelRef | null
  score: number
  min_approval_threshold: number
  meets_skill_threshold: boolean
  approved: boolean
  model_level_estimate: ModelLevelEstimate | null
  levels: ValidationLevelResult[]
  pose_detected_ratio: number | null
  duration_seconds: number | null
  notes: string[]
}

export interface UploadSamplePayload {
  file: File
  skillLevelId: string
  sampleRole: SampleRole
  criterionKey?: string | null
  participantId?: string | null
  signedConsent: boolean
}

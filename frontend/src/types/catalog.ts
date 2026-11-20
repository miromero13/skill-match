export interface Category {
  parent_id?: string | null
  id: string
  name: string
  slug: string
  description?: string | null
  is_active: boolean
}

export interface ChallengeType {
  id: string
  name: string
  code: string
  evaluation_modality: string
  description?: string | null
  is_active: boolean
}

/** Códigos de medición soportados por el motor de validación (S1). */
export const METRIC_REFERENCE_REPLICATION = "REFERENCE_REPLICATION"
export const METRIC_BALL_TOUCH_STREAK = "BALL_TOUCH_STREAK"

/** El backend puede incorporar nuevos códigos: se tipa como string abierto. */
export type MetricTypeCode = string

/** Elemento de `GET /api/admin/skill-lab/metric-types`. */
export interface MetricTypeInfo {
  code: MetricTypeCode
  name: string
  description: string
  requires_target: boolean
  requires_reference: boolean
}

export interface RubricCriterion {
  /** Identificador estable generado por el servidor; se conserva al editar. */
  key?: string
  name: string
  weight: number
  description: string
  /** Por defecto `REFERENCE_REPLICATION` cuando el criterio almacenado no lo trae. */
  metric_type?: MetricTypeCode
  /** Objetivo de la medición (p. ej. toques seguidos que valen el 100%). */
  target?: number | null
}

export interface Rubric {
  id?: string
  skill_level_id?: string
  instructions?: string | null
  min_score: number
  criteria: RubricCriterion[]
}

export interface SkillLevel {
  id?: string
  skill_id?: string
  level_number: number
  name: string
  description?: string | null
  rubric?: Rubric | null
}

export interface Skill {
  id: string
  category_id: string
  challenge_type_id?: string | null
  name: string
  slug: string
  description?: string | null
  min_approval_threshold: number
  is_ready_to_publish: boolean
  is_active: boolean
  levels: SkillLevel[]
}

export interface CreateCategoryPayload {
  parent_id?: string | null
  name: string
  description?: string
  is_active?: boolean
}

export interface UpdateCategoryPayload {
  parent_id?: string | null
  name?: string
  description?: string
  is_active?: boolean
}

export interface CreateChallengeTypePayload {
  name: string
  code: string
  evaluation_modality: string
  description?: string
  is_active?: boolean
}

export interface CreateSkillPayload {
  category_id: string
  name: string
  challenge_type_id?: string | null
  description?: string
  min_approval_threshold: number
  is_ready_to_publish?: boolean
  levels?: SkillLevel[]
}

export interface UpdateSkillPayload {
  category_id: string
  name: string
  challenge_type_id?: string | null
  description?: string
  min_approval_threshold: number
  is_ready_to_publish?: boolean
  is_active?: boolean
  levels?: SkillLevel[]
}

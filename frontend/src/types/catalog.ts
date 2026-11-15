export interface Category {
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

export interface RubricCriterion {
  name: string
  weight: number
  description: string
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
  name: string
  description?: string
  is_active?: boolean
}

export interface UpdateCategoryPayload {
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

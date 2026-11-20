export type UrgencyLevel = "LOW" | "MEDIUM" | "HIGH"

export interface SkillSummary {
  id: string
  name: string
  slug: string
  category_id: string
  category_name?: string | null
}

export interface UserLearningSkill {
  id: string
  user_id: string
  skill_id: string
  current_level: number
  target_level: number
  urgency: UrgencyLevel
  notes?: string | null
  skill?: SkillSummary | null
  created_at?: string | null
  updated_at?: string | null
}

export interface UserLearningSkillCreate {
  skill_id: string
  current_level: number
  target_level: number
  urgency: UrgencyLevel
  notes?: string | null
}

export interface UserLearningSkillUpdate {
  current_level?: number
  target_level?: number
  urgency?: UrgencyLevel
  notes?: string | null
}

export interface CatalogSkillOption {
  id: string
  name: string
  slug: string
  category_id: string
  description?: string | null
}

export interface TutorSearchFilters {
  query?: string
  skill_id?: string
  category_id?: string
  min_level?: string
  verified_only?: boolean
  modality?: "VIRTUAL" | "PRESENCIAL" | "BOTH"
  max_distance?: number
  latitude?: number
  longitude?: number
  sort_by?: "reputation" | "distance" | "points_asc" | "points_desc" | "experience" | "recent"
  page?: number
  page_size?: number
}

export interface TutorTeachingSkill {
  id: string
  skill_id: string
  skill_name: string
  category_id: string
  category_name: string
  declared_level: string
  years_of_experience: number
  description?: string | null
  accepts_points: boolean
  hourly_points_rate?: number | null
  status: string
  is_verified: boolean
}

export interface TutorSearchResult {
  id: string
  full_name: string
  avatar_url?: string | null
  bio?: string | null
  location_label?: string | null
  latitude?: number | null
  longitude?: number | null
  exchange_modality: "VIRTUAL" | "PRESENCIAL" | "BOTH"
  presencial_radius_km: number
  distance_km?: number | null
  rating: number
  total_reviews: number
  has_verified_skills: boolean
  skills: TutorTeachingSkill[]
  created_at?: string | null
}

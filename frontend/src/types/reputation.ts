export interface SessionReview {
  id: string
  session_id: string
  reviewer_id: string
  reviewer_name: string
  reviewer_avatar?: string | null
  reviewed_id: string
  role_in_session: "INSTRUCTOR" | "LEARNER"
  rating_punctuality: number
  rating_pedagogy: number
  rating_domain: number
  overall_rating: number
  comment?: string | null
  created_at: string
}

export interface CreateSessionReviewPayload {
  rating_punctuality: number
  rating_pedagogy: number
  rating_domain: number
  comment?: string | null
}

export interface SendSessionTipPayload {
  amount: number
  note?: string | null
}

export interface SessionReviewState {
  session_id: string
  can_review: boolean
  has_reviewed: boolean
  reviewed_by_counterpart: boolean
  existing_review?: SessionReview | null
}

export interface ReputationBadge {
  code: string
  title: string
  description: string
  icon: string
  is_active: boolean
}

export interface RatingsBreakdown {
  punctuality: number
  pedagogy: number
  domain: number
}

export interface TrustScoreFactors {
  ia_verified_score: number
  peer_feedback_score: number
  attendance_score: number
  tenure_score: number
}

export interface UserReputation {
  user_id: string
  full_name: string
  avatar_url?: string | null
  trust_score: number
  overall_rating: number
  total_reviews: number
  ratings_breakdown: RatingsBreakdown
  factors: TrustScoreFactors
  badges: ReputationBadge[]
  recent_reviews: SessionReview[]
}

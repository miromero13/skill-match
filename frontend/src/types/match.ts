export interface MatchSuggestion {
    id: string
    counterpart_name: string
    counterpart_avatar_url: string | null
    member_name: string
    member_avatar_url: string | null
    you_verified: string[]
    they_verified: string[]
    status: string
    you_teach: string[]
    they_teach: string[]
    compatibility_score?: number | null
}

export interface FactorBreakdown {
    score: number
    weight: number
    weighted_score: number
    description: string
}

export interface CompatibilityFactors {
    skill_affinity: FactorBreakdown
    schedule_overlap: FactorBreakdown
    modality_location: FactorBreakdown
    reputation_verification: FactorBreakdown
}

export interface MatchCompatibility {
    match_id: string | null
    counterpart_id: string
    counterpart_name: string
    compatibility_score: number
    factors: CompatibilityFactors
    match_reasons: string[]
}

export interface MatchSuggestion {
    id: string
    counterpart_name: string
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

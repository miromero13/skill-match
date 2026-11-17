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

}

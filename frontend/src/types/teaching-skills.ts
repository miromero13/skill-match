export const declaredLevels = [
    { value: "BEGINNER", label: "Principiante" },
    { value: "INTERMEDIATE", label: "Intermedio" },
    { value: "ADVANCED", label: "Avanzado" },
    { value: "EXPERT", label: "Experto" },
] as const

export type DeclaredLevel = typeof declaredLevels[number]["value"]

export interface TeachingSkill {
    id: string
    skill_id: string
    skill_name: string
    declared_level: DeclaredLevel
    years_of_experience: number
    description: string | null
    accepts_points: boolean
    hourly_points_rate: number | null
    status: string
}

export interface TeachingSkillPayload {
    skill_id: string
    declared_level: DeclaredLevel
    years_of_experience: number
    description: string | null
    accepts_points: boolean
    hourly_points_rate: number | null
}

export interface AvailableSkill {
    id: string
    name: string
}

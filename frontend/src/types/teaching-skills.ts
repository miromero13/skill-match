export const declaredLevels = [
    { value: "BEGINNER", label: "Principiante" },
    { value: "INTERMEDIATE", label: "Intermedio" },
    { value: "ADVANCED", label: "Avanzado" },
    { value: "EXPERT", label: "Experto" },
] as const

export type DeclaredLevel = (typeof declaredLevels)[number]["value"]
export interface AvailableSkill {
    id: string
    name: string
}

export interface TeachingSkillPayload {
    skill_id: string
    declared_level: DeclaredLevel
    years_of_experence: number
    description: string | null
    accepts_points: boolean
    hourly_points_rate: number | null
}

export interface TeachingSkill extends TeachingSkillPayload {
    id: string
    skill_name: string
    status: string
}
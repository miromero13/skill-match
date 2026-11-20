export const declaredLevels = [
    { value: "BEGINNER", label: "Nivel 1 · Principiante", levelNumber: 1 },
    { value: "INTERMEDIATE", label: "Nivel 3 · Intermedio", levelNumber: 3 },
    { value: "ADVANCED", label: "Nivel 4 · Avanzado", levelNumber: 4 },
    { value: "EXPERT", label: "Nivel 5 · Experto / Master Pedagogo", levelNumber: 5 },
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
    category_id?: string
}

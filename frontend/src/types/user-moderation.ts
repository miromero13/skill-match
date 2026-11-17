export type ReportReason =
    | "HARASSMENT"
    | "PAYMENT_OUTSIDE"
    | "NO_SHOW"
    | "SPAM_FRAUD"
    | "OTHER"

export const REPORT_REASON_LABELS: Record<ReportReason, string> = {
    HARASSMENT: "Conducta, lenguaje ofensivo o acoso durante la interacción",
    PAYMENT_OUTSIDE: "Solicitud de dinero o pago por fuera de SkillMatch",
    NO_SHOW: "Inasistencias reiteradas sin aviso previo (No-Shows)",
    SPAM_FRAUD: "Spam, contenido fraudulento o identidad falsa",
    OTHER: "Otro motivo no listado",
}

export interface BlockedUser {
    block_id: string
    user_id: string
    full_name: string
    avatar_url: string | null
    reason: string | null
    blocked_at: string
}

export interface ReportUserPayload {
    reason: ReportReason
    description: string
    evidence_url?: string | null
    block_user: boolean
}

export interface ReportUserResult {
    report_id: string
    reported_id: string
    reported_name: string
    reason: string
    status: string
    created_at: string
    user_blocked: boolean
}

export interface UserSafetyStatus {
    target_user_id: string
    is_blocked_by_me: boolean
    is_blocking_me: boolean
    can_interact: boolean
    blocked_at: string | null
}

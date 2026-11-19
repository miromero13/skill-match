/**
 * Contratos de datos TypeScript para el Centro de Quejas, Resolución de Disputas
 * y Compensación en SkillPoints (HU-43 / RF-GOV-01, RF-GOV-02, RF-GOV-03).
 */

export type ComplaintStatus = 'OPEN' | 'RESOLVED' | 'DISMISSED'

export type ComplaintReason =
  | 'NO_SHOW'
  | 'POOR_QUALITY'
  | 'INAPPROPRIATE_BEHAVIOR'
  | 'PAYMENT_DISPUTE'
  | 'TECHNICAL_ISSUES'
  | 'OTHER'

export interface Complaint {
  id: string
  user_id: string
  user_full_name?: string | null
  user_email?: string | null
  session_id?: string | null
  session_reference?: string | null
  reason: ComplaintReason
  title: string
  description: string
  evidence_urls: string[]
  status: ComplaintStatus
  admin_response?: string | null
  points_compensated: number
  resolved_by_id?: string | null
  resolved_by_name?: string | null
  resolved_at?: string | null
  created_at: string
  updated_at?: string | null
}

export interface ComplaintCreatePayload {
  title: string
  reason: ComplaintReason
  description: string
  session_id?: string | null
  evidence_urls?: string[]
}

export interface ComplaintResolvePayload {
  status: 'RESOLVED' | 'DISMISSED'
  admin_response: string
  points_to_compensate?: number
}

export const COMPLAINT_REASON_LABELS: Record<ComplaintReason, string> = {
  NO_SHOW: 'Inasistencia del tutor / participante',
  POOR_QUALITY: 'Baja calidad o contenido no acorde',
  INAPPROPRIATE_BEHAVIOR: 'Conducta inapropiada / falta de respeto',
  PAYMENT_DISPUTE: 'Disputa de pago o cobro de puntos',
  TECHNICAL_ISSUES: 'Problemas técnicos o de conexión',
  OTHER: 'Otro motivo no clasificado',
}

export const COMPLAINT_STATUS_LABELS: Record<ComplaintStatus, string> = {
  OPEN: 'Abierta / En Revisión',
  RESOLVED: 'Resuelta',
  DISMISSED: 'Desestimada',
}

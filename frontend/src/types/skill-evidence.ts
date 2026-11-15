export const evidenceTypes = [
  { value: "REPOSITORY", label: "Repositorio" },
  { value: "VIDEO", label: "Video" },
  { value: "CERTIFICATE", label: "Certificado" },
  { value: "OTHER", label: "Otro" },
] as const

export type EvidenceType = (typeof evidenceTypes)[number]["value"]
export interface EvidencePayload {
  title: string
  description: string | null
  url: string
  evidence_type: EvidenceType
}
export interface SkillEvidence extends EvidencePayload {
  id: string
  teaching_skill_id: string
  created_at: string
  updated_at: string
}
export type EvidenceErrors = Partial<Record<keyof EvidencePayload, string>>

export function isEvidenceType(value: string): value is EvidenceType {
  return evidenceTypes.some((type) => type.value === value)
}

export function safeEvidenceUrl(value: string): string | null {
  const trimmed = value.trim()
  if (!/^https?:\/\//i.test(trimmed)) return null
  const authority = trimmed.match(/^https?:\/\/([^/?#]*)/i)?.[1]
  if (!authority || authority.includes("@")) return null
  try {
    const url = new URL(trimmed)
    if (
      !["http:", "https:"].includes(url.protocol) ||
      url.username ||
      url.password
    )
      return null
    return url.href
  } catch {
    return null
  }
}

export function validateEvidence(value: EvidencePayload): EvidenceErrors {
  const errors: EvidenceErrors = {}
  const length = Array.from(value.title.trim()).length
  if (!length || length > 150)
    errors.title = "Escribe un título de entre 1 y 150 caracteres."
  if (Array.from(value.description?.trim() ?? "").length > 2000)
    errors.description = "La descripción admite hasta 2000 caracteres."
  const url = safeEvidenceUrl(value.url)
  if (!url || value.url.trim().length > 2048 || url.length > 2048)
    errors.url =
      "Usa una URL HTTP o HTTPS sin credenciales, de hasta 2048 caracteres."
  if (!isEvidenceType(value.evidence_type))
    errors.evidence_type = "Selecciona un tipo de evidencia."
  return errors
}

export function evidencePayload(value: EvidencePayload): EvidencePayload {
  return {
    title: value.title.trim(),
    description: value.description?.trim() || null,
    url: safeEvidenceUrl(value.url) ?? value.url.trim(),
    evidence_type: value.evidence_type,
  }
}

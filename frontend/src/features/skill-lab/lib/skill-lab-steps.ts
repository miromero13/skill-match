import { METRIC_REFERENCE_REPLICATION } from "@/types/catalog"
import type { SkillLabConfig, SkillLabLevel } from "../types"

/** Pasos del asistente del laboratorio (S8): un paso por nivel, luego entrenamiento y validación. */

export type LevelStepStatus = "complete" | "missing-reference" | "no-training"
export type SkillLabStepStatus = LevelStepStatus | "untrained" | "neutral"

interface StepBase {
  /** Texto corto del indicador ("Nivel 1", "Entrenamiento"). */
  label: string
  /** Nombre completo usado en "Paso X de Y — …" y "Siguiente: …". */
  title: string
}

export type SkillLabStep =
  | (StepBase & { kind: "level"; level: SkillLabLevel; status: LevelStepStatus })
  | (StepBase & { kind: "training"; status: "complete" | "untrained" })
  | (StepBase & { kind: "validation"; status: "neutral" })

export const STEP_STATUS_LABEL: Record<SkillLabStepStatus, string> = {
  complete: "Completo",
  "missing-reference": "Falta referencia",
  "no-training": "Sin videos de entrenamiento",
  untrained: "Sin entrenar",
  neutral: "Opcional",
}

export const PASO_PARAM = "paso"

export function sortLevels(levels: readonly SkillLabLevel[]): SkillLabLevel[] {
  return [...levels].sort((a, b) => a.level_number - b.level_number)
}

export function levelTitle(level: Pick<SkillLabLevel, "level_number" | "name">): string {
  return `Nivel ${level.level_number} · ${level.name}`
}

/**
 * Misma regla que `_readiness_issues` del backend: un nivel sin criterios se evalúa como una replicación implícita,
 * y la referencia del nivel hace falta cuando algún criterio REFERENCE_REPLICATION no tiene su propia referencia.
 */
export function levelNeedsLevelReference(level: SkillLabLevel): boolean {
  if (level.criteria.length === 0) return true
  return level.criteria.some(
    (criterion) =>
      (criterion.metric_type || METRIC_REFERENCE_REPLICATION) === METRIC_REFERENCE_REPLICATION &&
      !criterion.has_reference
  )
}

export function levelHasRequiredReferences(level: SkillLabLevel): boolean {
  return !levelNeedsLevelReference(level) || level.reference !== null
}

export function levelStepStatus(level: SkillLabLevel): LevelStepStatus {
  if (!levelHasRequiredReferences(level)) return "missing-reference"
  if (level.training_samples < 1) return "no-training"
  return "complete"
}

/** Aviso no bloqueante al salir de un nivel incompleto; `null` cuando el nivel está completo. */
export function incompleteLevelMessage(level: SkillLabLevel): string | null {
  const status = levelStepStatus(level)
  if (status === "missing-reference") return `${levelTitle(level)} quedó incompleto: falta el video de referencia.`
  if (status === "no-training") return `${levelTitle(level)} quedó incompleto: no tiene videos de entrenamiento.`
  return null
}

export function buildSkillLabSteps(config: Pick<SkillLabConfig, "levels" | "active_model">): SkillLabStep[] {
  const levelSteps: SkillLabStep[] = sortLevels(config.levels).map((level) => ({
    kind: "level",
    label: `Nivel ${level.level_number}`,
    title: levelTitle(level),
    level,
    status: levelStepStatus(level),
  }))
  return [
    ...levelSteps,
    {
      kind: "training",
      label: "Entrenamiento",
      title: "Entrenamiento",
      status: config.active_model ? "complete" : "untrained",
    },
    { kind: "validation", label: "Probar validación", title: "Probar validación", status: "neutral" },
  ]
}

/** Convierte `?paso=` (1-based) en un número válido dentro de 1..total. */
export function clampStepNumber(raw: string | null, total: number): number {
  const max = Math.max(1, total)
  const parsed = raw === null ? Number.NaN : Number.parseInt(raw, 10)
  if (!Number.isFinite(parsed) || parsed < 1) return 1
  return Math.min(parsed, max)
}

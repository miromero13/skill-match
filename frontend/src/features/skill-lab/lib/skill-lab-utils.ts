import {
  METRIC_BALL_TOUCH_STREAK,
  METRIC_REFERENCE_REPLICATION,
  type MetricTypeCode,
  type MetricTypeInfo,
  type RubricCriterion,
} from "@/types/catalog"
import { ApiError } from "@/types/api"

export const SKILL_LAB_VIDEO_ACCEPT =
  "video/mp4,video/webm,video/quicktime,.mp4,.webm,.mov"

/** Respaldo cuando `GET /admin/skill-lab/metric-types` no está disponible. */
export const DEFAULT_METRIC_TYPES: MetricTypeInfo[] = [
  {
    code: METRIC_REFERENCE_REPLICATION,
    name: "Replicar video de referencia",
    description: "Compara la postura y el movimiento con el video de referencia del nivel.",
    requires_target: false,
    requires_reference: true,
  },
  {
    code: METRIC_BALL_TOUCH_STREAK,
    name: "Toques seguidos con balón",
    description: "Cuenta los toques consecutivos; el objetivo equivale al 100%.",
    requires_target: true,
    requires_reference: false,
  },
]

const WEIGHT_TOLERANCE = 0.01

export function roundTo2(value: number): number {
  return Math.round(value * 100) / 100
}

export function formatPercent(value: number): string {
  return String(roundTo2(value))
}

export function sumCriteriaWeights(criteria: readonly Pick<RubricCriterion, "weight">[]): number {
  return roundTo2(criteria.reduce((total, criterion) => total + (Number(criterion.weight) || 0), 0))
}

export function isWeightsTotalValid(total: number): boolean {
  return Math.abs(total - 100) <= WEIGHT_TOLERANCE
}

/** Mismo texto que rechaza el backend (S1). */
export function weightsTotalErrorMessage(levelName: string, total: number): string {
  return `Los porcentajes de los criterios del nivel «${levelName}» deben sumar 100% (actual: ${formatPercent(total)}%).`
}

export function findMetricType(
  metricTypes: readonly MetricTypeInfo[],
  code: MetricTypeCode | null | undefined
): MetricTypeInfo | undefined {
  const effective = code || METRIC_REFERENCE_REPLICATION
  return (
    metricTypes.find((item) => item.code === effective) ??
    DEFAULT_METRIC_TYPES.find((item) => item.code === effective)
  )
}

export function metricTypeLabel(
  metricTypes: readonly MetricTypeInfo[],
  code: MetricTypeCode | null | undefined
): string {
  return findMetricType(metricTypes, code)?.name ?? (code || METRIC_REFERENCE_REPLICATION)
}

export function metricRequiresTarget(
  metricTypes: readonly MetricTypeInfo[],
  code: MetricTypeCode | null | undefined
): boolean {
  return findMetricType(metricTypes, code)?.requires_target ?? false
}

export function targetLabel(code: MetricTypeCode | null | undefined): string {
  return code === METRIC_BALL_TOUCH_STREAK ? "Objetivo (toques seguidos)" : "Objetivo"
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function formatDateTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString("es", { dateStyle: "medium", timeStyle: "short" })
}

export const NEUTRAL_REQUEST_FAILURE =
  "No se pudo conectar con el servidor. Verificá la conexión e intentá de nuevo."

/** statuscode 0 = fallo de red/transporte: el mensaje no proviene del APIResponse. */
export function requestFailureMessage(error: unknown, fallback = NEUTRAL_REQUEST_FAILURE): string {
  if (error instanceof ApiError && error.statuscode > 0 && error.message) {
    return error.message
  }
  return fallback
}

/** Estilo ámbar no destructivo para avisos del motor y fallos de transporte (S6). */
export const WARNING_ALERT_CLASS =
  "border-amber-500/40 bg-amber-500/5 text-amber-800 dark:text-amber-300"

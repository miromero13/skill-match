import { CheckCircle2, Info, XCircle } from "lucide-react"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import type { MetricTypeInfo } from "@/types/catalog"
import { formatPercent, metricTypeLabel, WARNING_ALERT_CLASS } from "../lib/skill-lab-utils"
import type { SkillValidationResult, ValidationLevelResult } from "../types"

function clampScore(score: number | null): number {
  if (score === null || Number.isNaN(score)) return 0
  return Math.min(100, Math.max(0, score))
}

function LevelStatusBadge({ level }: { level: ValidationLevelResult }) {
  if (!level.evaluable) {
    return (
      <Badge variant="outline" className="border-amber-500/40 text-amber-700 dark:text-amber-300">
        No evaluable
      </Badge>
    )
  }
  return level.passed ? (
    <Badge variant="outline" className="border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300">
      Superado
    </Badge>
  ) : (
    <Badge variant="outline">No superado</Badge>
  )
}

interface ValidationResultViewProps {
  result: SkillValidationResult
  metricTypes: MetricTypeInfo[]
}

export function ValidationResultView({ result, metricTypes }: ValidationResultViewProps) {
  const levels = [...result.levels].sort((a, b) => a.level_number - b.level_number)
  const score = clampScore(result.score)

  return (
    <div className="space-y-4" data-testid="skill-lab-validation-result">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <Badge
            data-testid="skill-lab-achieved-level"
            variant="outline"
            className={
              result.achieved_level
                ? "h-6 border-emerald-500/40 bg-emerald-500/10 px-3 text-sm text-emerald-700 dark:text-emerald-300"
                : "h-6 px-3 text-sm"
            }
          >
            {result.achieved_level ? (
              <>
                <span className="sr-only">Nivel alcanzado: </span>
                {`Nivel ${result.achieved_level.level_number} · ${result.achieved_level.name}`}
              </>
            ) : (
              "Sin nivel alcanzado"
            )}
          </Badge>
          <Badge
            data-testid="skill-lab-approved"
            variant="outline"
            className={
              result.approved
                ? "h-6 border-emerald-500/40 bg-emerald-500/10 px-3 text-sm font-semibold text-emerald-700 dark:text-emerald-300"
                : "h-6 px-3 text-sm font-semibold text-muted-foreground"
            }
          >
            {result.approved ? <CheckCircle2 /> : <XCircle />}
            {result.approved ? "Aprobado" : "No aprobado"}
            <span className="font-normal">{`(mín. ${formatPercent(result.min_approval_threshold)}%)`}</span>
          </Badge>
        </div>
        <p className="text-3xl font-bold text-foreground tabular-nums" data-testid="skill-lab-score">
          {formatPercent(score)}
          <span className="text-base font-medium text-muted-foreground">/100</span>
        </p>
      </div>
      <Progress value={score} aria-label="Puntaje obtenido" />

      {result.model_level_estimate && (
        <p data-testid="skill-lab-model-estimate" className="text-xs text-muted-foreground">
          {`Estimación: ${result.model_level_estimate.name} (${formatPercent(
            result.model_level_estimate.confidence * 100
          )}%)`}
        </p>
      )}

      {result.notes.length > 0 && (
        <Alert variant="default" className={WARNING_ALERT_CLASS} data-testid="skill-lab-result-notes">
          <Info />
          <AlertTitle>Observaciones</AlertTitle>
          <AlertDescription className="text-amber-800/90 dark:text-amber-300/90">
            <ul className="list-disc space-y-0.5 pl-4">
              {result.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      <Accordion type="multiple" defaultValue={[]} className="rounded-lg border border-border/60 px-3">
        {levels.map((level) => (
          <AccordionItem key={level.level_id} value={level.level_id} data-testid={`skill-lab-result-level-${level.level_id}`}>
            <AccordionTrigger className="py-3">
              <span className="flex flex-1 flex-wrap items-center gap-2 pr-2">
                <span className="font-semibold">{`Nivel ${level.level_number} · ${level.name}`}</span>
                <span className="text-xs text-muted-foreground tabular-nums">
                  {level.evaluable
                    ? `${formatPercent(clampScore(level.score))} / mín. ${formatPercent(level.min_score)}`
                    : `mín. ${formatPercent(level.min_score)}`}
                </span>
                <LevelStatusBadge level={level} />
              </span>
            </AccordionTrigger>
            <AccordionContent className="space-y-3">
              {!level.evaluable && level.not_evaluable_reason && (
                <Alert
                  variant="default"
                  className={WARNING_ALERT_CLASS}
                  data-testid={`skill-lab-not-evaluable-${level.level_id}`}
                >
                  <Info />
                  <AlertDescription className="text-amber-800/90 dark:text-amber-300/90">
                    {level.not_evaluable_reason}
                  </AlertDescription>
                </Alert>
              )}
              <ul className="space-y-3">
                {level.criteria.map((criterion) => (
                  <li key={criterion.key} className="space-y-1">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex min-w-0 flex-wrap items-center gap-1.5">
                        <span className="font-medium text-foreground">{criterion.name}</span>
                        <Badge variant="secondary">{`${formatPercent(criterion.weight)}%`}</Badge>
                        <span className="text-xs text-muted-foreground">
                          {metricTypeLabel(metricTypes, criterion.metric_type)}
                        </span>
                      </div>
                      <span className="text-xs font-semibold tabular-nums">
                        {criterion.evaluable ? `${formatPercent(clampScore(criterion.score))}/100` : "No evaluable"}
                      </span>
                    </div>
                    <Progress value={criterion.evaluable ? clampScore(criterion.score) : 0} aria-label={`Puntaje de ${criterion.name}`} />
                    {criterion.note && (
                      <p className="text-xs text-amber-700 dark:text-amber-400">{criterion.note}</p>
                    )}
                  </li>
                ))}
              </ul>
            </AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>

      <p className="text-[11px] break-words text-muted-foreground">
        Motor <span className="font-mono">{result.engine_version}</span> · Modelo{" "}
        <span className="font-mono">{result.model_version ?? "sin calibrar"}</span>
        {result.pose_detected_ratio !== null && ` · Persona ${formatPercent(result.pose_detected_ratio * 100)}%`}
        {result.duration_seconds !== null && ` · ${result.duration_seconds.toFixed(1)} s`}
      </p>
    </div>
  )
}

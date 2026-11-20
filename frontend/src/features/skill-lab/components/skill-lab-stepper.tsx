import { AlertTriangle, CheckCircle2, CircleDashed, FlaskConical } from "lucide-react"
import { cn } from "cn"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { STEP_STATUS_LABEL, type SkillLabStep, type SkillLabStepStatus } from "../lib/skill-lab-steps"

/** Icono + tono por estado: el estado nunca se comunica solo con color. */
const STATUS_META: Record<SkillLabStepStatus, { icon: typeof CheckCircle2; tone: string }> = {
  complete: { icon: CheckCircle2, tone: "text-emerald-600 dark:text-emerald-400" },
  "missing-reference": { icon: AlertTriangle, tone: "text-amber-700 dark:text-amber-400" },
  "no-training": { icon: CircleDashed, tone: "text-muted-foreground" },
  untrained: { icon: CircleDashed, tone: "text-muted-foreground" },
  neutral: { icon: FlaskConical, tone: "text-muted-foreground" },
}

export function SkillLabStepStatusBadge({ status, className }: { status: SkillLabStepStatus; className?: string }) {
  const { icon: Icon, tone } = STATUS_META[status]
  return (
    <Badge variant="outline" className={cn("shrink-0 border-border/60", tone, className)}>
      <Icon />
      {STEP_STATUS_LABEL[status]}
    </Badge>
  )
}

interface SkillLabStepperProps {
  steps: SkillLabStep[]
  /** Paso actual, 1-based. */
  current: number
  onSelect: (step: number) => void
}

/** Indicador de pasos (S8): fila numerada con conectores en tablet/escritorio, resumen + progreso en móvil. */
export function SkillLabStepper({ steps, current, onSelect }: SkillLabStepperProps) {
  const total = steps.length
  const currentStep = steps[current - 1]

  return (
    <nav aria-label="Pasos del laboratorio" className="space-y-3">
      <div className="space-y-2 md:hidden">
        <div className="flex items-center justify-between gap-2">
          <p data-testid="skill-lab-step-summary" className="min-w-0 truncate text-sm font-semibold text-foreground">
            {`Paso ${current} de ${total} — ${currentStep.title}`}
          </p>
          <SkillLabStepStatusBadge status={currentStep.status} />
        </div>
        <Progress value={(current / total) * 100} aria-label="Progreso del laboratorio" />
      </div>

      <ol className="flex items-center gap-1 overflow-x-auto pb-1 md:gap-0">
        {steps.map((step, index) => {
          const number = index + 1
          const isCurrent = number === current
          const { icon: StatusIcon, tone } = STATUS_META[step.status]
          const showStatus = step.status !== "neutral"
          const statusLabel = STEP_STATUS_LABEL[step.status]
          return (
            <li key={`${step.kind}-${step.title}`} className="flex shrink-0 items-center md:min-w-0 md:flex-1 md:last:flex-none">
              <Button
                type="button"
                variant={isCurrent ? "outline" : "ghost"}
                aria-current={isCurrent ? "step" : undefined}
                aria-label={`Paso ${number}: ${step.title} — ${statusLabel}`}
                data-testid={`skill-lab-step-${number}`}
                data-status={step.status}
                onClick={() => onSelect(number)}
                className={cn(
                  "h-auto gap-2 px-2 py-1.5 md:max-w-[13rem] md:justify-start",
                  isCurrent && "border-emerald-500/50 bg-emerald-500/5"
                )}
              >
                <span
                  aria-hidden="true"
                  className={cn(
                    "relative flex size-7 shrink-0 items-center justify-center rounded-full border text-xs font-semibold tabular-nums",
                    isCurrent
                      ? "border-emerald-600 bg-emerald-600 text-white"
                      : "border-border bg-background text-muted-foreground"
                  )}
                >
                  {number}
                  <StatusIcon
                    className={cn(
                      "absolute -right-1 -bottom-1 size-3.5! rounded-full bg-background md:hidden",
                      tone
                    )}
                  />
                </span>
                <span className="hidden min-w-0 flex-col items-start gap-0.5 text-left md:flex">
                  <span className="max-w-full truncate text-xs font-semibold text-foreground">
                    {step.kind === "level" ? `${step.label} · ${step.level.name}` : step.label}
                  </span>
                  {showStatus && (
                    <SkillLabStepStatusBadge status={step.status} className="h-4 px-1.5 text-[10px] [&>svg]:size-2.5!" />
                  )}
                </span>
              </Button>
              {number < total && (
                <span
                  aria-hidden="true"
                  className={cn(
                    "mx-1 hidden h-px min-w-4 flex-1 md:block",
                    step.status === "complete" ? "bg-emerald-500/60" : "bg-border"
                  )}
                />
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

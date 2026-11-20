import { useEffect, useMemo, useRef, useState } from "react"
import { Info } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import type { MetricTypeInfo } from "@/types/catalog"
import { useSkillLabStep } from "../hooks/use-skill-lab-step"
import { buildSkillLabSteps, incompleteLevelMessage, sortLevels } from "../lib/skill-lab-steps"
import { WARNING_ALERT_CLASS } from "../lib/skill-lab-utils"
import type { SkillLabConfig, SkillLabSample } from "../types"
import { LevelCard } from "./level-card"
import { SkillLabStepFooter } from "./skill-lab-step-footer"
import { SkillLabStepper } from "./skill-lab-stepper"
import { TrainingCard } from "./training-card"
import { ValidationCard } from "./validation-card"

interface SkillLabWizardProps {
  skillId: string
  config: SkillLabConfig
  samples: SkillLabSample[]
  metricTypes: MetricTypeInfo[]
  reload: () => void | Promise<void>
}

interface IncompleteHint {
  message: string
  /** Paso (1-based) del nivel incompleto que se dejó. */
  step: number
}

/** Asistente paso a paso del laboratorio (S8): cada nivel, entrenamiento y prueba de validación. */
export function SkillLabWizard({ skillId, config, samples, metricTypes, reload }: SkillLabWizardProps) {
  const steps = useMemo(() => buildSkillLabSteps(config), [config])
  const levels = useMemo(() => sortLevels(config.levels), [config.levels])
  const { current, goTo } = useSkillLabStep(steps.length)
  const [hint, setHint] = useState<IncompleteHint | null>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const previousStepRef = useRef(current)

  const step = steps[current - 1]
  const nextStep = current < steps.length ? steps[current] : null

  useEffect(() => {
    if (previousStepRef.current === current) return
    previousStepRef.current = current
    contentRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
  }, [current])

  /** La navegación nunca se bloquea: al salir de un nivel incompleto solo se deja un aviso en línea. */
  const navigate = (target: number) => {
    if (target === current) return
    const message = step.kind === "level" ? incompleteLevelMessage(step.level) : null
    setHint(message ? { message, step: current } : null)
    goTo(target)
  }

  const visibleHint = hint && hint.step !== current ? hint : null

  return (
    <div className="space-y-6">
      {levels.length === 0 && (
        <p className="rounded-lg border border-dashed border-border/60 p-6 text-center text-sm text-muted-foreground">
          Sin niveles en el catálogo.
        </p>
      )}

      <SkillLabStepper steps={steps} current={current} onSelect={navigate} />

      <div ref={contentRef} data-testid="skill-lab-step-content" className="scroll-mt-4 space-y-4">
        {visibleHint && (
          <Alert variant="default" className={WARNING_ALERT_CLASS} data-testid="skill-lab-incomplete-hint">
            <Info />
            <AlertDescription className="flex flex-col gap-2 text-amber-800/90 sm:flex-row sm:items-center sm:justify-between dark:text-amber-300/90">
              <span>{visibleHint.message}</span>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => navigate(visibleHint.step)}
                className="self-start sm:self-auto"
              >
                Volver al nivel
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {step.kind === "level" && (
          <LevelCard
            key={step.level.id}
            skillId={skillId}
            level={step.level}
            samples={samples}
            metricTypes={metricTypes}
            onChanged={reload}
          />
        )}
        {step.kind === "training" && (
          <TrainingCard skillId={skillId} levels={levels} activeModel={config.active_model} onTrained={reload} />
        )}
        {step.kind === "validation" && <ValidationCard skillId={skillId} levels={levels} metricTypes={metricTypes} />}
      </div>

      <SkillLabStepFooter
        current={current}
        total={steps.length}
        nextTitle={nextStep?.title ?? null}
        onPrevious={() => navigate(current - 1)}
        onNext={() => navigate(current + 1)}
      />
    </div>
  )
}

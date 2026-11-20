import { useState, type ReactNode } from "react"
import { BrainCircuit, ChevronDown, Info, Loader2 } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { skillLabApi } from "../api/skill-lab-api"
import {
  formatDateTime,
  formatPercent,
  requestFailureMessage,
  WARNING_ALERT_CLASS,
} from "../lib/skill-lab-utils"
import type { SkillLabLevel, SkillLabModel } from "../types"
import { InfoTip } from "./info-tip"

interface TrainingCardProps {
  skillId: string
  levels: SkillLabLevel[]
  activeModel: SkillLabModel | null
  onTrained: () => void | Promise<void>
}

function KeyNumber({ label, value, info }: { label: string; value: string; info?: ReactNode }) {
  return (
    <div className="space-y-0.5">
      <p className="flex items-center gap-1 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
        {label}
        {info}
      </p>
      <p className="text-xl font-semibold tabular-nums">{value}</p>
    </div>
  )
}

function ModelSummary({ model, levels }: { model: SkillLabModel; levels: SkillLabLevel[] }) {
  const [detailsOpen, setDetailsOpen] = useState(false)
  const metrics = model.metricas ?? {}
  const perLevel = Object.entries(metrics.samples_per_level ?? {})
  const levelName = (key: string) =>
    levels.find((level) => level.id === key || String(level.level_number) === key)?.name ?? key
  const accuracy = typeof metrics.loo_level_accuracy === "number" ? metrics.loo_level_accuracy : null
  const notes = Array.isArray(metrics.notes) ? metrics.notes : []
  const totalVideos = perLevel.reduce((total, [, count]) => total + (Number(count) || 0), 0)

  return (
    <div data-testid="skill-lab-active-model" className="space-y-3 rounded-lg border border-border/60 p-3 text-sm">
      <p className="flex flex-wrap items-center gap-x-2">
        <span className="font-mono font-semibold text-foreground">{model.version}</span>
        <span className="text-xs text-muted-foreground">{formatDateTime(model.created_at)}</span>
      </p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <KeyNumber label="Videos" value={String(totalVideos)} />
        <KeyNumber label="Niveles" value={String(perLevel.length)} />
        {accuracy !== null && (
          <KeyNumber
            label="Precisión"
            value={`${formatPercent(accuracy * 100)}%`}
            info={<InfoTip label="Ayuda: precisión">Precisión de nivel dejando un video fuera.</InfoTip>}
          />
        )}
      </div>
      {notes.length > 0 && (
        <Alert variant="default" className={WARNING_ALERT_CLASS}>
          <Info />
          <AlertDescription className="text-amber-800/90 dark:text-amber-300/90">
            <ul className="list-disc space-y-0.5 pl-4">
              {notes.map((note) => (
                <li key={String(note)}>{String(note)}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}
      <Collapsible open={detailsOpen} onOpenChange={setDetailsOpen}>
        <CollapsibleTrigger asChild>
          <Button type="button" variant="link" size="sm" className="h-auto px-0 text-muted-foreground">
            Detalles
            <ChevronDown className={detailsOpen ? "rotate-180 transition-transform" : "transition-transform"} />
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent className="pt-2">
          {perLevel.length > 0 ? (
            <ul className="space-y-0.5 text-xs">
              {perLevel.map(([key, count]) => (
                <li key={key}>{`${levelName(key)}: ${count}`}</li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-muted-foreground">Tolerancias por defecto (sin videos).</p>
          )}
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
}

/** Calibración few-shot por habilidad (S5): ajusta tolerancias y prototipos con pocos videos. */
export function TrainingCard({ skillId, levels, activeModel, onTrained }: TrainingCardProps) {
  const [isTraining, setIsTraining] = useState(false)
  const [trainedModel, setTrainedModel] = useState<SkillLabModel | null>(null)
  const [error, setError] = useState<string | null>(null)
  const model = trainedModel ?? activeModel

  const train = async () => {
    if (isTraining) return
    setIsTraining(true)
    setError(null)
    try {
      const created = await skillLabApi.train(skillId)
      setTrainedModel(created)
      await onTrained()
    } catch (err) {
      setError(requestFailureMessage(err))
    } finally {
      setIsTraining(false)
    }
  }

  return (
    <Card className="border-border/60 shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-lg font-semibold">
          <BrainCircuit className="size-5 text-emerald-500" />
          Entrenamiento
          <InfoTip label="Ayuda: entrenamiento">
            Calibra el validador con pocos videos por nivel; funciona incluso sin videos usando tolerancias por
            defecto.
          </InfoTip>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Button type="button" onClick={train} disabled={isTraining} className="w-full sm:w-auto">
          {isTraining ? <Loader2 className="animate-spin" /> : <BrainCircuit />}
          {isTraining ? "Entrenando…" : "Entrenar modelo"}
        </Button>
        {error && (
          <Alert variant="default" className={WARNING_ALERT_CLASS}>
            <Info />
            <AlertDescription className="text-amber-800/90 dark:text-amber-300/90">{error}</AlertDescription>
          </Alert>
        )}
        {model ? (
          <ModelSummary model={model} levels={levels} />
        ) : (
          <p className="text-sm text-muted-foreground">Sin modelo entrenado.</p>
        )}
      </CardContent>
    </Card>
  )
}

import { useParams } from "react-router-dom"
import { AlertTriangle, Loader2, RotateCcw } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { useSkillLab } from "@/features/skill-lab/hooks/use-skill-lab"
import { useMetricTypes } from "@/features/skill-lab/hooks/use-metric-types"
import { SkillLabHeader } from "@/features/skill-lab/components/skill-lab-header"
import { SkillLabWizard } from "@/features/skill-lab/components/skill-lab-wizard"
import { WARNING_ALERT_CLASS } from "@/features/skill-lab/lib/skill-lab-utils"

/** Laboratorio de entrenamiento y validación de una habilidad del catálogo (S2-S6 y asistente por pasos S8, solo ADMIN). */
export function AdminSkillLabPage() {
  const { skillId } = useParams<{ skillId: string }>()
  const { config, samples, isLoading, loadError, reload } = useSkillLab(skillId)
  const metricTypes = useMetricTypes()

  if (isLoading && !config) {
    return (
      <div className="flex flex-col items-center justify-center p-16 text-muted-foreground">
        <Loader2 className="mb-2 size-8 animate-spin text-emerald-500" />
        <p className="text-sm">Cargando laboratorio…</p>
      </div>
    )
  }

  if (!config || !skillId) {
    return (
      <div className="mx-auto max-w-3xl p-4 md:p-8">
        <Alert variant="default" className={WARNING_ALERT_CLASS}>
          <AlertTriangle />
          <AlertTitle>No se pudo cargar el laboratorio</AlertTitle>
          <AlertDescription className="space-y-2 text-amber-800/90 dark:text-amber-300/90">
            <p>{loadError ?? "La habilidad no está disponible."}</p>
            <Button variant="outline" size="sm" onClick={() => void reload()}>
              <RotateCcw />
              Reintentar
            </Button>
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 pb-24 md:p-8">
      <SkillLabHeader config={config} />

      {loadError && (
        <Alert variant="default" className={WARNING_ALERT_CLASS}>
          <AlertTriangle />
          <AlertDescription className="text-amber-800/90 dark:text-amber-300/90">{loadError}</AlertDescription>
        </Alert>
      )}

      <SkillLabWizard
        skillId={skillId}
        config={config}
        samples={samples}
        metricTypes={metricTypes}
        reload={reload}
      />
    </div>
  )
}

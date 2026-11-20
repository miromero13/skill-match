import { Link } from "react-router-dom"
import { ArrowLeft, CheckCircle2, Cpu, FlaskConical, Info } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { formatPercent, WARNING_ALERT_CLASS } from "../lib/skill-lab-utils"
import type { SkillLabConfig } from "../types"

export function SkillLabHeader({ config }: { config: SkillLabConfig }) {
  const { skill, readiness } = config
  return (
    <div className="space-y-4">
      <Button asChild variant="ghost" size="sm" className="-ml-2 text-muted-foreground">
        <Link to="/admin/catalog">
          <ArrowLeft />
          Volver al catálogo
        </Link>
      </Button>

      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0 space-y-2">
          <p className="flex items-center gap-1.5 text-xs font-semibold tracking-wider text-emerald-600 uppercase dark:text-emerald-400">
            <FlaskConical className="size-3.5" />
            Laboratorio de validación
          </p>
          <h1 className="text-2xl font-extrabold tracking-tight break-words text-foreground md:text-3xl">
            {skill.name}
          </h1>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary">{skill.category.name}</Badge>
            <Badge variant="outline" className="border-indigo-500/40 text-indigo-600 dark:text-indigo-300">
              <Cpu />
              {skill.challenge_type
                ? `${skill.challenge_type.name} (${skill.challenge_type.evaluation_modality})`
                : "Sin tipo de desafío"}
            </Badge>
            <Badge
              variant="outline"
              className="border-emerald-500/40 bg-emerald-500/10 font-semibold text-emerald-700 dark:text-emerald-300"
            >
              {`Umbral mínimo ${formatPercent(skill.min_approval_threshold)}%`}
            </Badge>
          </div>
        </div>
      </div>

      {readiness.ready_to_validate && readiness.issues.length === 0 ? (
        <Alert
          variant="default"
          data-testid="skill-lab-readiness"
          className="border-emerald-500/40 bg-emerald-500/5 text-emerald-800 dark:text-emerald-300"
        >
          <CheckCircle2 />
          <AlertTitle>Listo para validar</AlertTitle>
          <AlertDescription className="text-emerald-800/90 dark:text-emerald-300/90">
            Todos los niveles tienen lo necesario para calificar videos.
          </AlertDescription>
        </Alert>
      ) : (
        <Alert variant="default" data-testid="skill-lab-readiness" className={WARNING_ALERT_CLASS}>
          <Info />
          <AlertTitle>Pendientes antes de validar</AlertTitle>
          <AlertDescription className="text-amber-800/90 dark:text-amber-300/90">
            {readiness.issues.length > 0 ? (
              <ul className="list-disc space-y-0.5 pl-4">
                {readiness.issues.map((issue) => (
                  <li key={issue}>{issue}</li>
                ))}
              </ul>
            ) : (
              <p>El laboratorio todavía no está listo para validar.</p>
            )}
          </AlertDescription>
        </Alert>
      )}
    </div>
  )
}

import { useState } from "react"
import { Trash2 } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { skillLabApi } from "../api/skill-lab-api"
import { formatDateTime, formatFileSize } from "../lib/skill-lab-utils"
import type { SkillLabLevel, SkillLabSample } from "../types"

interface TrainingSampleListProps {
  level: SkillLabLevel
  samples: SkillLabSample[]
  onChanged: () => void | Promise<void>
}

export function TrainingSampleList({ level, samples, onChanged }: TrainingSampleListProps) {
  const [pendingDelete, setPendingDelete] = useState<SkillLabSample | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

  const criterionName = (key: string | null) =>
    key ? level.criteria.find((criterion) => criterion.key === key)?.name ?? key : "Todo el nivel"

  const confirmDelete = async () => {
    if (!pendingDelete) return
    setIsDeleting(true)
    try {
      await skillLabApi.deleteSample(pendingDelete.id)
      await onChanged()
    } catch {
      // El apiClient ya mostró el mensaje del backend.
    } finally {
      setIsDeleting(false)
      setPendingDelete(null)
    }
  }

  if (samples.length === 0) {
    return <p className="text-xs text-muted-foreground">Todavía no hay videos de entrenamiento en este nivel.</p>
  }

  return (
    <>
      <ul className="divide-y divide-border/60 rounded-md border border-border/60">
        {samples.map((sample, index) => {
          const who = sample.participant_id ?? `#${index + 1}`
          return (
            <li key={sample.id} className="flex flex-col gap-1.5 p-2 text-xs sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0 space-y-1">
                <div className="flex flex-wrap items-center gap-1.5">
                  <Badge variant="secondary">{criterionName(sample.criterion_key)}</Badge>
                  <span className="text-muted-foreground">
                    {sample.file_format.toUpperCase()} · {formatFileSize(sample.file_size_bytes)} ·{" "}
                    {formatDateTime(sample.created_at)}
                  </span>
                  {sample.participant_id && (
                    <span className="font-medium text-foreground">{sample.participant_id}</span>
                  )}
                  <Badge
                    variant="outline"
                    className={
                      sample.analysis_ready
                        ? "border-emerald-500/40 text-emerald-700 dark:text-emerald-300"
                        : "border-amber-500/40 text-amber-700 dark:text-amber-300"
                    }
                  >
                    {sample.analysis_ready ? "Analizado" : "Análisis pendiente"}
                  </Badge>
                </div>
                {sample.analysis_notes.length > 0 && (
                  <ul className="list-disc pl-4 text-amber-700 dark:text-amber-400">
                    {sample.analysis_notes.map((note) => (
                      <li key={note}>{note}</li>
                    ))}
                  </ul>
                )}
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label={`Eliminar video de entrenamiento ${who}`}
                onClick={() => setPendingDelete(sample)}
                className="self-end text-muted-foreground hover:text-red-500 sm:self-auto"
              >
                <Trash2 />
              </Button>
            </li>
          )
        })}
      </ul>

      <AlertDialog open={pendingDelete !== null} onOpenChange={(open) => !open && !isDeleting && setPendingDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Eliminar este video de entrenamiento?</AlertDialogTitle>
            <AlertDialogDescription>
              El video dejará de usarse para entrenar el modelo de esta habilidad. Esta acción no se puede deshacer.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={isDeleting}
              onClick={(event) => {
                event.preventDefault()
                void confirmDelete()
              }}
            >
              Eliminar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

import * as React from "react"
import {
  Pencil,
  Trash2,
  Sparkles,
  TrendingUp,
  Clock,
  Flame,
  CheckCircle2,
} from "lucide-react"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
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
import type { UserLearningSkill, UrgencyLevel } from "@/types/learning-skill"
import { useLearningSkillStore } from "@/stores/learning-skill-store"

const LEVEL_NAMES: Record<number, string> = {
  1: "Principiante",
  2: "Elemental",
  3: "Intermedio",
  4: "Avanzado",
  5: "Master",
}

interface LearningSkillCardProps {
  item: UserLearningSkill
  onEdit: (item: UserLearningSkill) => void
}

export function LearningSkillCard({ item, onEdit }: LearningSkillCardProps) {
  const { deleteLearningSkill } = useLearningSkillStore()
  const [showDeleteConfirm, setShowDeleteConfirm] = React.useState(false)
  const [isDeleting, setIsDeleting] = React.useState(false)

  const handleDelete = async () => {
    setIsDeleting(true)
    await deleteLearningSkill(item.id)
    setIsDeleting(false)
    setShowDeleteConfirm(false)
  }

  const renderUrgencyBadge = (urgency: UrgencyLevel) => {
    switch (urgency) {
      case "HIGH":
        return (
          <Badge className="bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/30 gap-1 text-[10px] font-semibold">
            <Flame className="h-3 w-3" />
            <span>Prioridad Alta</span>
          </Badge>
        )
      case "MEDIUM":
        return (
          <Badge className="bg-primary/10 text-primary border border-primary/30 gap-1 text-[10px] font-semibold">
            <TrendingUp className="h-3 w-3" />
            <span>Prioridad Media</span>
          </Badge>
        )
      case "LOW":
      default:
        return (
          <Badge variant="outline" className="text-muted-foreground gap-1 text-[10px] font-medium">
            <Clock className="h-3 w-3" />
            <span>Prioridad Baja</span>
          </Badge>
        )
    }
  }

  const progressPercent = Math.min(100, (item.current_level / item.target_level) * 100)

  return (
    <>
      <Card className="rounded-2xl border border-border/70 hover:border-primary/40 shadow-xs hover:shadow-md transition-all bg-card overflow-hidden">
        <CardHeader className="p-4 pb-3 flex flex-row items-start justify-between gap-3 space-y-0">
          <div className="space-y-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                {item.skill?.category_name || "Catálogo"}
              </span>
              {renderUrgencyBadge(item.urgency)}
            </div>
            <h3 className="text-base font-bold text-foreground leading-snug">
              {item.skill?.name || "Habilidad de Aprendizaje"}
            </h3>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-muted-foreground hover:text-foreground rounded-lg"
              onClick={() => onEdit(item)}
              title="Editar meta"
            >
              <Pencil className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-muted-foreground hover:text-destructive rounded-lg"
              onClick={() => setShowDeleteConfirm(true)}
              title="Eliminar habilidad"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        </CardHeader>

        <CardContent className="p-4 pt-1 space-y-3">
          {/* Trayecto de Niveles */}
          <div className="p-3 rounded-xl bg-muted/40 border border-border/50 space-y-2">
            <div className="flex items-center justify-between text-xs">
              <div className="space-y-0.5">
                <span className="text-[10px] text-muted-foreground block">Nivel Actual</span>
                <span className="font-semibold text-foreground">
                  Nivel {item.current_level} ({LEVEL_NAMES[item.current_level] || "Inicial"})
                </span>
              </div>
              <div className="text-right space-y-0.5">
                <span className="text-[10px] text-muted-foreground block">Nivel Meta</span>
                <span className="font-semibold text-primary flex items-center gap-1 justify-end">
                  <CheckCircle2 className="h-3 w-3" />
                  Nivel {item.target_level} ({LEVEL_NAMES[item.target_level] || "Objetivo"})
                </span>
              </div>
            </div>

            {/* Barra de Progresión */}
            <div className="w-full bg-border/60 h-2 rounded-full overflow-hidden">
              <div
                className="bg-primary h-full transition-all duration-300 rounded-full"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>

          {/* Notas */}
          {item.notes && (
            <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed italic">
              "{item.notes}"
            </p>
          )}

          {/* Sello de coincidencia formativa */}
          <div className="pt-1 flex items-center justify-between text-[11px] text-muted-foreground">
            <span className="inline-flex items-center gap-1 text-primary text-[10px] font-semibold">
              <Sparkles className="h-3 w-3" />
              <span>Visible para matching recíproco</span>
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Modal de confirmación de eliminación */}
      <AlertDialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <AlertDialogContent className="rounded-2xl">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-base font-bold">
              ¿Eliminar habilidad de tu lista?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-xs text-muted-foreground">
              Dejarás de recibir propuestas de intercambio para{" "}
              <strong className="text-foreground">{item.skill?.name}</strong>. Podrás volver a
              agregarla en cualquier momento.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting} className="text-xs">
              Cancelar
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={isDeleting}
              className="bg-destructive hover:bg-destructive/90 text-destructive-foreground text-xs font-semibold"
            >
              {isDeleting ? "Eliminando..." : "Sí, eliminar"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

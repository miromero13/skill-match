import * as React from "react"
import { Pencil, AlertCircle, Loader2 } from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { useLearningSkillStore } from "@/stores/learning-skill-store"
import type { UserLearningSkill, UrgencyLevel } from "@/types/learning-skill"

const LEVEL_LABELS: Record<number, string> = {
  1: "Nivel 1 - Principiante",
  2: "Nivel 2 - Elemental",
  3: "Nivel 3 - Intermedio",
  4: "Nivel 4 - Avanzado",
  5: "Nivel 5 - Master",
}

interface EditLearningSkillDialogProps {
  item: UserLearningSkill | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function EditLearningSkillDialog({
  item,
  open,
  onOpenChange,
}: EditLearningSkillDialogProps) {
  const { updateLearningSkill } = useLearningSkillStore()

  const [currentLevel, setCurrentLevel] = React.useState(1)
  const [targetLevel, setTargetLevel] = React.useState(3)
  const [urgency, setUrgency] = React.useState<UrgencyLevel>("MEDIUM")
  const [notes, setNotes] = React.useState("")
  const [isSubmitting, setIsSubmitting] = React.useState(false)

  React.useEffect(() => {
    if (item) {
      setCurrentLevel(item.current_level)
      setTargetLevel(item.target_level)
      setUrgency(item.urgency)
      setNotes(item.notes || "")
    }
  }, [item])

  if (!item) return null

  const isInvalidLevel = targetLevel < currentLevel

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (isInvalidLevel) return

    setIsSubmitting(true)
    const success = await updateLearningSkill(item.id, {
      current_level: currentLevel,
      target_level: targetLevel,
      urgency,
      notes: notes.trim() || null,
    })

    setIsSubmitting(false)
    if (success) {
      onOpenChange(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px] rounded-2xl">
        <form onSubmit={handleSubmit} className="space-y-4">
          <DialogHeader className="space-y-1">
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="text-primary border-primary/30">
                {item.skill?.category_name || "Catálogo"}
              </Badge>
            </div>
            <DialogTitle className="text-lg font-bold flex items-center gap-2">
              <Pencil className="h-4 w-4 text-primary" />
              <span>Editar: {item.skill?.name || "Habilidad"}</span>
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Ajusta tu nivel de partida, el objetivo al que aspiras y el grado de prioridad.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 pt-2">
            {/* Niveles: Actual vs Meta */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="edit-current-level" className="text-xs font-semibold">
                  Nivel de Partida
                </Label>
                <Select
                  value={String(currentLevel)}
                  onValueChange={(v) => setCurrentLevel(Number(v))}
                >
                  <SelectTrigger id="edit-current-level" className="w-full h-10 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {[1, 2, 3, 4, 5].map((lvl) => (
                      <SelectItem key={lvl} value={String(lvl)} className="text-xs">
                        {LEVEL_LABELS[lvl]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="edit-target-level" className="text-xs font-semibold">
                  Nivel Meta
                </Label>
                <Select
                  value={String(targetLevel)}
                  onValueChange={(v) => setTargetLevel(Number(v))}
                >
                  <SelectTrigger id="edit-target-level" className="w-full h-10 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {[1, 2, 3, 4, 5].map((lvl) => (
                      <SelectItem key={lvl} value={String(lvl)} className="text-xs">
                        {LEVEL_LABELS[lvl]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Error si el nivel meta es menor al actual */}
            {isInvalidLevel && (
              <div className="flex items-center gap-2 p-2.5 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-xs">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>El nivel meta no puede ser inferior a tu nivel actual.</span>
              </div>
            )}

            {/* Urgencia */}
            <div className="space-y-1.5">
              <Label htmlFor="edit-urgency" className="text-xs font-semibold">
                Nivel de Urgencia
              </Label>
              <Select
                value={urgency}
                onValueChange={(v) => setUrgency(v as UrgencyLevel)}
              >
                <SelectTrigger id="edit-urgency" className="w-full h-10 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="LOW" className="text-xs">
                    Baja (Interés casual / A mi propio ritmo)
                  </SelectItem>
                  <SelectItem value="MEDIUM" className="text-xs">
                    Media (Meta trimestral / Aprendizaje regular)
                  </SelectItem>
                  <SelectItem value="HIGH" className="text-xs">
                    Alta (Urgente / Proyecto o necesidad inmediata)
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Notas */}
            <div className="space-y-1.5">
              <Label htmlFor="edit-notes" className="text-xs font-semibold">
                Notas u Objetivos
              </Label>
              <Textarea
                id="edit-notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                maxLength={500}
                className="text-xs min-h-[65px] resize-none"
              />
            </div>
          </div>

          <DialogFooter className="pt-2 gap-2 sm:gap-0">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => onOpenChange(false)}
              disabled={isSubmitting}
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={isInvalidLevel || isSubmitting}
              className="gap-2 bg-primary hover:bg-primary/90 text-primary-foreground font-semibold"
            >
              {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
              <span>Guardar Cambios</span>
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

import * as React from "react"
import { Plus, BookOpen, AlertCircle, Loader2 } from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
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
import { useLearningSkillStore } from "@/stores/learning-skill-store"
import type { UrgencyLevel } from "@/types/learning-skill"

const LEVEL_LABELS: Record<number, string> = {
  1: "Nivel 1 - Principiante (Desde cero)",
  2: "Nivel 2 - Elemental (Conceptos básicos)",
  3: "Nivel 3 - Intermedio (Autonomía funcional)",
  4: "Nivel 4 - Avanzado (Alta solvencia)",
  5: "Nivel 5 - Master (Dominio experto)",
}

interface AddLearningSkillDialogProps {
  open?: boolean
  onOpenChange?: (open: boolean) => void
  trigger?: React.ReactNode
}

export function AddLearningSkillDialog({
  open: controlledOpen,
  onOpenChange: setControlledOpen,
  trigger,
}: AddLearningSkillDialogProps) {
  const [internalOpen, setInternalOpen] = React.useState(false)
  const isControlled = controlledOpen !== undefined
  const open = isControlled ? controlledOpen : internalOpen
  const setOpen = isControlled ? setControlledOpen! : setInternalOpen

  const { catalogSkills, fetchCatalogSkills, addLearningSkill, learningSkills } =
    useLearningSkillStore()

  const [selectedSkillId, setSelectedSkillId] = React.useState("")
  const [currentLevel, setCurrentLevel] = React.useState(1)
  const [targetLevel, setTargetLevel] = React.useState(3)
  const [urgency, setUrgency] = React.useState<UrgencyLevel>("MEDIUM")
  const [notes, setNotes] = React.useState("")
  const [isSubmitting, setIsSubmitting] = React.useState(false)

  React.useEffect(() => {
    if (open) {
      fetchCatalogSkills()
    }
  }, [open, fetchCatalogSkills])

  // Filtrar habilidades que el usuario ya tenga agregadas
  const registeredSkillIds = new Set(learningSkills.map((item) => item.skill_id))
  const availableSkills = catalogSkills.filter((s) => !registeredSkillIds.has(s.id))

  const isInvalidLevel = targetLevel < currentLevel

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedSkillId || isInvalidLevel) return

    setIsSubmitting(true)
    const success = await addLearningSkill({
      skill_id: selectedSkillId,
      current_level: currentLevel,
      target_level: targetLevel,
      urgency,
      notes: notes.trim() || null,
    })

    setIsSubmitting(false)
    if (success) {
      setSelectedSkillId("")
      setCurrentLevel(1)
      setTargetLevel(3)
      setUrgency("MEDIUM")
      setNotes("")
      setOpen(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {trigger ? (
        <DialogTrigger asChild>{trigger}</DialogTrigger>
      ) : (
        <DialogTrigger asChild>
          <Button className="gap-2 bg-primary hover:bg-primary/90 text-primary-foreground font-semibold shadow-xs">
            <Plus className="h-4 w-4" />
            <span>Agregar Habilidad a Aprender</span>
          </Button>
        </DialogTrigger>
      )}

      <DialogContent className="sm:max-w-[520px] rounded-2xl">
        <form onSubmit={handleSubmit} className="space-y-4">
          <DialogHeader className="space-y-1">
            <div className="flex items-center gap-2 text-primary font-bold text-xs uppercase tracking-wider">
              <BookOpen className="h-4 w-4" />
              <span>Demanda de Aprendizaje (HU-15)</span>
            </div>
            <DialogTitle className="text-xl font-bold">
              ¿Qué habilidad deseas aprender?
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Define tu nivel de partida y el nivel meta que buscas alcanzar. El motor de
              coincidencias te conectará con instructores afines.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 pt-2">
            {/* Selector de Habilidad */}
            <div className="space-y-1.5">
              <Label htmlFor="skill-select" className="text-xs font-semibold">
                Habilidad del Catálogo Maestro *
              </Label>
              <Select
                value={selectedSkillId}
                onValueChange={setSelectedSkillId}
                required
              >
                <SelectTrigger id="skill-select" className="w-full h-10 text-xs">
                  <SelectValue placeholder="Selecciona una habilidad para aprender..." />
                </SelectTrigger>
                <SelectContent>
                  {availableSkills.length === 0 ? (
                    <div className="p-3 text-xs text-muted-foreground text-center">
                      No hay más habilidades disponibles en el catálogo
                    </div>
                  ) : (
                    availableSkills.map((skill) => (
                      <SelectItem key={skill.id} value={skill.id} className="text-xs">
                        {skill.name}
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
            </div>

            {/* Niveles: Actual vs Meta */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="current-level" className="text-xs font-semibold">
                  Nivel de Partida (Actual) *
                </Label>
                <Select
                  value={String(currentLevel)}
                  onValueChange={(v) => setCurrentLevel(Number(v))}
                >
                  <SelectTrigger id="current-level" className="w-full h-10 text-xs">
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
                <Label htmlFor="target-level" className="text-xs font-semibold">
                  Nivel Objetivo (Meta) *
                </Label>
                <Select
                  value={String(targetLevel)}
                  onValueChange={(v) => setTargetLevel(Number(v))}
                >
                  <SelectTrigger id="target-level" className="w-full h-10 text-xs">
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
                <span>
                  El nivel meta debe ser igual o superior a tu nivel de partida.
                </span>
              </div>
            )}

            {/* Nivel de Urgencia */}
            <div className="space-y-1.5">
              <Label htmlFor="urgency-select" className="text-xs font-semibold">
                Nivel de Urgencia / Prioridad *
              </Label>
              <Select
                value={urgency}
                onValueChange={(v) => setUrgency(v as UrgencyLevel)}
              >
                <SelectTrigger id="urgency-select" className="w-full h-10 text-xs">
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

            {/* Notas opcionales */}
            <div className="space-y-1.5">
              <Label htmlFor="notes-input" className="text-xs font-semibold">
                Objetivos o Notas de Aprendizaje (Opcional)
              </Label>
              <Textarea
                id="notes-input"
                placeholder="Ej. Deseo aprender para aplicarlo en un proyecto laboral o examen..."
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                maxLength={500}
                className="text-xs min-h-[70px] resize-none"
              />
              <span className="text-[10px] text-muted-foreground block text-right">
                {notes.length}/500 caracteres
              </span>
            </div>
          </div>

          <DialogFooter className="pt-2 gap-2 sm:gap-0">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setOpen(false)}
              disabled={isSubmitting}
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={!selectedSkillId || isInvalidLevel || isSubmitting}
              className="gap-2 bg-primary hover:bg-primary/90 text-primary-foreground font-semibold"
            >
              {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
              <span>Registrar Habilidad</span>
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

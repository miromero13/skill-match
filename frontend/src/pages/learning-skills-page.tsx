import * as React from "react"
import {
  BookOpen,
  Plus,
  TrendingUp,
  Target,
  Compass,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useLearningSkillStore } from "@/stores/learning-skill-store"
import { LearningSkillCard } from "@/components/learning-skills/learning-skill-card"
import { AddLearningSkillDialog } from "@/components/learning-skills/add-learning-skill-dialog"
import { EditLearningSkillDialog } from "@/components/learning-skills/edit-learning-skill-dialog"
import type { UserLearningSkill } from "@/types/learning-skill"

export function LearningSkillsPage() {
  const { learningSkills, isLoading, fetchLearningSkills } = useLearningSkillStore()

  const [isAddOpen, setIsAddOpen] = React.useState(false)
  const [editingItem, setEditingItem] = React.useState<UserLearningSkill | null>(null)

  React.useEffect(() => {
    fetchLearningSkills()
  }, [fetchLearningSkills])

  const highPriorityCount = learningSkills.filter((s) => s.urgency === "HIGH").length
  const avgTargetLevel =
    learningSkills.length > 0
      ? (
          learningSkills.reduce((acc, curr) => acc + curr.target_level, 0) /
          learningSkills.length
        ).toFixed(1)
      : "0.0"

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-12">
      {/* Encabezado Principal */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border/60 pb-5">
        <div className="space-y-1">
          <div className="inline-flex items-center gap-1.5 text-primary text-xs font-bold uppercase tracking-wider">
            <BookOpen className="h-4 w-4" />
            <span>Demanda Formativa & Intercambio (HU-15)</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-foreground">
            Habilidades que Deseo Aprender
          </h1>
          <p className="text-xs sm:text-sm text-muted-foreground max-w-2xl">
            Registra los conocimientos que deseas adquirir con tu nivel de partida y nivel meta.
            El motor de coincidencias te emparejará con miembros instructores afines.
          </p>
        </div>

        <div className="shrink-0">
          <AddLearningSkillDialog
            open={isAddOpen}
            onOpenChange={setIsAddOpen}
            trigger={
              <Button className="w-full sm:w-auto gap-2 bg-primary hover:bg-primary/90 text-primary-foreground font-semibold shadow-sm">
                <Plus className="h-4 w-4" />
                <span>Agregar Habilidad</span>
              </Button>
            }
          />
        </div>
      </div>

      {/* Métricas Rápidas */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <Card className="rounded-2xl border border-border/70 bg-card p-4 shadow-xs">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary shrink-0">
              <BookOpen className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[11px] text-muted-foreground font-medium">Demandas Activas</p>
              <p className="text-xl font-bold text-foreground">{learningSkills.length}</p>
            </div>
          </div>
        </Card>

        <Card className="rounded-2xl border border-border/70 bg-card p-4 shadow-xs">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-red-500/10 flex items-center justify-center text-red-500 shrink-0">
              <TrendingUp className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[11px] text-muted-foreground font-medium">Prioridad Alta</p>
              <p className="text-xl font-bold text-foreground">{highPriorityCount}</p>
            </div>
          </div>
        </Card>

        <Card className="rounded-2xl border border-border/70 bg-card p-4 shadow-xs">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary shrink-0">
              <Target className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[11px] text-muted-foreground font-medium">Nivel Meta Promedio</p>
              <p className="text-xl font-bold text-foreground">Nivel {avgTargetLevel}</p>
            </div>
          </div>
        </Card>
      </div>

      {/* Grid de Habilidades o Estado Vacío */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="rounded-2xl p-4 space-y-3">
              <Skeleton className="h-4 w-1/3" />
              <Skeleton className="h-6 w-2/3" />
              <Skeleton className="h-16 w-full rounded-xl" />
            </Card>
          ))}
        </div>
      ) : learningSkills.length === 0 ? (
        <Card className="rounded-3xl border-dashed border-2 border-border/80 bg-card/50 p-8 sm:p-12 text-center">
          <CardContent className="flex flex-col items-center max-w-md mx-auto space-y-4 p-0">
            <div className="h-16 w-16 rounded-3xl bg-primary/10 flex items-center justify-center text-primary shadow-inner">
              <Compass className="h-8 w-8" />
            </div>
            <div className="space-y-1">
              <h3 className="text-lg font-bold text-foreground">
                No tienes habilidades registradas aún
              </h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Agrega las competencias o disciplinas que deseas aprender (ej. Python, Guitarra o Fútbol).
                El sistema las cruzará con los instructores certificados disponibles.
              </p>
            </div>
            <Button
              onClick={() => setIsAddOpen(true)}
              className="gap-2 bg-primary hover:bg-primary/90 text-primary-foreground font-semibold mt-2"
            >
              <Plus className="h-4 w-4" />
              <span>Explorar Catálogo y Agregar</span>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Listado de tus metas de aprendizaje</span>
            <span className="font-semibold">{learningSkills.length} registradas</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {learningSkills.map((item) => (
              <LearningSkillCard
                key={item.id}
                item={item}
                onEdit={(it) => setEditingItem(it)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Diálogo de Edición */}
      <EditLearningSkillDialog
        item={editingItem}
        open={Boolean(editingItem)}
        onOpenChange={(isOpen) => !isOpen && setEditingItem(null)}
      />
    </div>
  )
}

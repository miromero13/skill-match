import { useEffect, useState } from "react"
import { useLearningSkillStore } from "@/stores/learning-skill-store"
import { LearningSkillCard } from "@/components/learning-skills/learning-skill-card"
import { AddLearningSkillDialog } from "@/components/learning-skills/add-learning-skill-dialog"
import { EditLearningSkillDialog } from "@/components/learning-skills/edit-learning-skill-dialog"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Plus } from "lucide-react"
import type { UserLearningSkill } from "@/types/learning-skill"

export function LearningSkillsSection() {
  const { learningSkills, isLoading, fetchLearningSkills } = useLearningSkillStore()
  const [isAddOpen, setIsAddOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<UserLearningSkill | null>(null)

  useEffect(() => {
    fetchLearningSkills()
  }, [fetchLearningSkills])

  return (
    <section className="mx-auto w-full max-w-4xl space-y-6 p-4 md:p-6" aria-label="Habilidades que deseo aprender">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold">Habilidades que deseo aprender</h2>
          <p className="text-sm text-muted-foreground">
            Tus metas formativas para emparejarte con instructores compatibles.
          </p>
        </div>
        <AddLearningSkillDialog
          open={isAddOpen}
          onOpenChange={setIsAddOpen}
          trigger={
            <Button className="gap-2">
              <Plus className="h-4 w-4" />
              <span>Agregar meta</span>
            </Button>
          }
        />
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {[1, 2].map((i) => (
            <Card key={i} className="p-4 space-y-3">
              <Skeleton className="h-4 w-1/3" />
              <Skeleton className="h-6 w-2/3" />
              <Skeleton className="h-16 w-full rounded-xl" />
            </Card>
          ))}
        </div>
      ) : learningSkills.length === 0 ? (
        <p className="text-sm text-muted-foreground">Todavía no registraste habilidades que deseas aprender.</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {learningSkills.map((item) => (
            <LearningSkillCard
              key={item.id}
              item={item}
              onEdit={(skill) => setEditingItem(skill)}
            />
          ))}
        </div>
      )}

      <EditLearningSkillDialog
        item={editingItem}
        open={Boolean(editingItem)}
        onOpenChange={(open) => !open && setEditingItem(null)}
      />
    </section>
  )
}

import { useState, useEffect } from "react"
import { ArrowLeftRight, CheckCircle2, Sparkles } from "lucide-react"
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
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { useLearningSkillStore } from "@/stores/learning-skill-store"
import { toast } from "sonner"
import type { TutorSearchResult } from "@/types/search"
import { CompatibilityBadge } from "@/components/matches/compatibility-badge"

interface ProposalDialogProps {
  tutor: TutorSearchResult | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function ProposalDialog({ tutor, open, onOpenChange }: ProposalDialogProps) {
  const { fetchLearningSkills } = useLearningSkillStore()
  const [selectedSkillId, setSelectedSkillId] = useState<string>("")
  const [proposalMessage, setProposalMessage] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    if (open) {
      fetchLearningSkills()
      setProposalMessage("")
      setSelectedSkillId("")
    }
  }, [open, fetchLearningSkills])

  const handleSendProposal = async () => {
    if (!tutor) return
    setIsSubmitting(true)

    // Simulación de envío de propuesta formal bilateral (HU-20 / HU-21)
    setTimeout(() => {
      setIsSubmitting(false)
      onOpenChange(false)
      toast.success(`¡Propuesta de intercambio enviada a ${tutor.full_name}!`)
    }, 600)
  }

  if (!tutor) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <div className="flex items-center justify-between gap-2 pr-6">
            <DialogTitle className="flex items-center gap-2 text-base font-semibold">
              <ArrowLeftRight className="h-5 w-5 text-primary" />
              Proponer Intercambio a {tutor.full_name}
            </DialogTitle>
            <CompatibilityBadge counterpartId={tutor.id} size="sm" />
          </div>
          <DialogDescription className="text-xs">
            Selecciona la habilidad que deseas aprender con {tutor.full_name} y envía un mensaje inicial de presentación.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Habilidades que enseña el tutor */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold">Habilidad que deseas aprender:</Label>
            <div className="grid grid-cols-1 gap-2">
              {tutor.skills.map((skill) => (
                <div
                  key={skill.id}
                  onClick={() => setSelectedSkillId(skill.id)}
                  className={`flex cursor-pointer items-center justify-between rounded-lg border p-2.5 text-xs transition-colors ${
                    selectedSkillId === skill.id
                      ? "border-primary bg-primary/10"
                      : "border-border hover:bg-muted/50"
                  }`}
                >
                  <div>
                    <span className="font-semibold text-foreground block">{skill.skill_name}</span>
                    <span className="text-[11px] text-muted-foreground">{skill.category_name}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Badge variant="outline" className="text-[10px]">
                      {skill.declared_level}
                    </Badge>
                    {selectedSkillId === skill.id && (
                      <CheckCircle2 className="h-4 w-4 text-primary" />
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Mensaje opcional */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold">Mensaje o propuesta de horarios:</Label>
            <Textarea
              placeholder={`Hola ${tutor.full_name}, me gustaría aprender contigo y coordinar una sesión...`}
              value={proposalMessage}
              onChange={(e) => setProposalMessage(e.target.value)}
              className="min-h-[80px] text-xs resize-none"
            />
          </div>
        </div>

        <DialogFooter className="flex sm:justify-between items-center gap-2">
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
            type="button"
            size="sm"
            onClick={handleSendProposal}
            disabled={!selectedSkillId || isSubmitting}
            className="gap-1.5 bg-primary text-primary-foreground hover:bg-primary/90"
          >
            <Sparkles className="h-4 w-4" />
            {isSubmitting ? "Enviando..." : "Enviar Propuesta"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

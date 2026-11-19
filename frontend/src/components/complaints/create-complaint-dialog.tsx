/**
 * Diálogo modal para que los miembros radiquen una queja formal (HU-43 / Vistas 24B, 26B).
 * Utiliza estrictamente componentes Shadcn/ui (preset Mist).
 */
import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useComplaintStore } from '@/stores/complaint-store'
import type { ComplaintReason } from '@/types/complaint'
import { COMPLAINT_REASON_LABELS } from '@/types/complaint'
import { AlertCircle, Plus, Trash2, ShieldAlert } from 'lucide-react'

interface CreateComplaintDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess?: () => void
}

export function CreateComplaintDialog({
  open,
  onOpenChange,
  onSuccess,
}: CreateComplaintDialogProps) {
  const { createComplaint, isSubmitting } = useComplaintStore()

  const [title, setTitle] = useState('')
  const [reason, setReason] = useState<ComplaintReason>('NO_SHOW')
  const [description, setDescription] = useState('')
  const [evidenceInput, setEvidenceInput] = useState('')
  const [evidenceUrls, setEvidenceUrls] = useState<string[]>([])
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const handleAddEvidence = () => {
    const trimmed = evidenceInput.trim()
    if (!trimmed) return
    if (!trimmed.startsWith('http://') && !trimmed.startsWith('https://')) {
      setErrorMsg('El enlace de evidencia debe ser una URL válida (http:// o https://)')
      return
    }
    if (evidenceUrls.includes(trimmed)) {
      setErrorMsg('Esta URL ya fue añadida como prueba.')
      return
    }
    setEvidenceUrls([...evidenceUrls, trimmed])
    setEvidenceInput('')
    setErrorMsg(null)
  }

  const handleRemoveEvidence = (index: number) => {
    setEvidenceUrls(evidenceUrls.filter((_, i) => i !== index))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMsg(null)

    if (!title.trim()) {
      setErrorMsg('Por favor ingresa un título para la queja.')
      return
    }
    if (description.trim().length < 10) {
      setErrorMsg('La descripción de los hechos debe tener al menos 10 caracteres.')
      return
    }

    const ok = await createComplaint({
      title: title.trim(),
      reason,
      description: description.trim(),
      evidence_urls: evidenceUrls,
    })

    if (ok) {
      // Limpiar formulario y cerrar
      setTitle('')
      setReason('NO_SHOW')
      setDescription('')
      setEvidenceUrls([])
      setEvidenceInput('')
      onOpenChange(false)
      onSuccess?.()
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg bg-card text-card-foreground border-border">
        <form onSubmit={handleSubmit} className="space-y-4">
          <DialogHeader>
            <div className="flex items-center gap-2 text-primary">
              <ShieldAlert className="h-5 w-5" />
              <DialogTitle className="text-lg font-bold">
                Radicar Queja o Disputa Formal
              </DialogTitle>
            </div>
            <DialogDescription className="text-xs text-muted-foreground">
              Expón con claridad la situación ocurrida. Un mediador del equipo
              administrativo revisará el caso y podrá arbitrar compensación en SkillPoints.
            </DialogDescription>
          </DialogHeader>

          {errorMsg && (
            <div className="flex items-center gap-2 p-3 text-xs rounded-lg bg-destructive/10 text-destructive border border-destructive/20">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="complaint-title" className="text-xs font-semibold">
                Título del Reclamo *
              </Label>
              <Input
                id="complaint-title"
                placeholder="Ej. Tutor no asistió a la sesión de Python"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                maxLength={255}
                required
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="complaint-reason" className="text-xs font-semibold">
                Motivo Principal *
              </Label>
              <Select
                value={reason}
                onValueChange={(val) => setReason(val as ComplaintReason)}
              >
                <SelectTrigger id="complaint-reason">
                  <SelectValue placeholder="Selecciona un motivo" />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(COMPLAINT_REASON_LABELS).map(([key, label]) => (
                    <SelectItem key={key} value={key}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="complaint-description" className="text-xs font-semibold">
                Descripción Detallada de los Hechos *
              </Label>
              <Textarea
                id="complaint-description"
                placeholder="Explica qué sucedió, fecha, acuerdos previos y cualquier detalle relevante para la mediación..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={4}
                required
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="evidence-input" className="text-xs font-semibold">
                Enlaces a Evidencias (Capturas, enlaces Drive, grabaciones)
              </Label>
              <div className="flex gap-2">
                <Input
                  id="evidence-input"
                  placeholder="https://..."
                  value={evidenceInput}
                  onChange={(e) => setEvidenceInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      handleAddEvidence()
                    }
                  }}
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleAddEvidence}
                  className="shrink-0"
                >
                  <Plus className="h-4 w-4 mr-1" /> Añadir
                </Button>
              </div>

              {evidenceUrls.length > 0 && (
                <div className="mt-2 space-y-1.5 max-h-28 overflow-y-auto">
                  {evidenceUrls.map((url, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between gap-2 p-1.5 px-2.5 rounded bg-muted text-xs"
                    >
                      <span className="truncate text-muted-foreground">{url}</span>
                      <button
                        type="button"
                        onClick={() => handleRemoveEvidence(idx)}
                        className="text-destructive hover:opacity-80 shrink-0"
                        title="Eliminar prueba"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <DialogFooter className="gap-2 sm:gap-0 pt-2 border-t border-border">
            <Button
              type="button"
              variant="ghost"
              onClick={() => onOpenChange(false)}
              disabled={isSubmitting}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Radicando...' : 'Enviar Queja Formal'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

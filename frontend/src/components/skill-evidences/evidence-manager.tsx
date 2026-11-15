import { useEffect, useRef, useState } from "react"
import { FileText, Loader2, Pencil, Plus, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Skeleton } from "@/components/ui/skeleton"
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
} from "@/components/ui/alert-dialog"
import { useSkillEvidenceStore } from "@/stores/skill-evidence-store"
import type { SkillEvidence } from "@/types/skill-evidence"
import { EvidenceLinks } from "./evidence-links"
import { EvidenceForm } from "./evidence-form"

function EvidencePanel({ skillId }: { skillId: string }) {
  const {
    items,
    total,
    page,
    loading,
    mutating,
    error,
    load,
    save,
    remove,
    reset,
  } = useSkillEvidenceStore()
  const [editing, setEditing] = useState<SkillEvidence | null | undefined>(
    undefined
  )
  const [deleting, setDeleting] = useState<SkillEvidence | null>(null)
  const deleteTrigger = useRef<HTMLButtonElement | null>(null)
  const addTrigger = useRef<HTMLButtonElement | null>(null)
  useEffect(() => {
    void load(skillId)
    return reset
  }, [skillId, load, reset])
  return (
    <>
      {error && (
        <Alert variant="destructive">
          <AlertDescription className="break-words">{error}</AlertDescription>
        </Alert>
      )}
      {editing !== undefined ? (
        <EvidenceForm
          initial={editing ?? undefined}
          saving={mutating}
          onCancel={() => setEditing(undefined)}
          onSave={async (payload) => {
            if (await save(payload, editing?.id)) setEditing(undefined)
          }}
        />
      ) : (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-sm text-muted-foreground" role="status">
              {loading
                ? "Cargando evidencias…"
                : `${total} evidencias externas`}
            </span>
            <Button
              ref={addTrigger}
              onClick={() => setEditing(null)}
              disabled={loading || mutating}
            >
              <Plus /> Agregar evidencia
            </Button>
          </div>
          {loading ? (
            <div className="space-y-3" aria-label="Cargando evidencias">
              <Skeleton className="h-32" />
              <Skeleton className="h-32" />
            </div>
          ) : (
            <>
              {error && (
                <Button
                  variant="outline"
                  onClick={() => void load(skillId, page)}
                  disabled={mutating}
                >
                  Reintentar
                </Button>
              )}
              {!error && items.length === 0 && (
                <div className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
                  <FileText className="mx-auto mb-3 size-8" />
                  Todavía no hay evidencias. Comparte un repositorio, video o
                  certificado externo.
                </div>
              )}
              <EvidenceLinks
                items={items}
                actions={(item) => (
                  <>
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={mutating}
                      onClick={() => setEditing(item)}
                      aria-label={`Editar ${item.title}`}
                    >
                      <Pencil /> Editar
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      disabled={mutating}
                      onClick={(event) => {
                        deleteTrigger.current = event.currentTarget
                        setDeleting(item)
                      }}
                      aria-label={`Eliminar ${item.title}`}
                    >
                      <Trash2 /> Eliminar
                    </Button>
                  </>
                )}
              />
              {total > 0 && (
                <div className="flex flex-wrap items-center justify-between gap-2 border-t pt-3">
                  <Button
                    variant="outline"
                    disabled={page <= 1 || mutating}
                    onClick={() => void load(skillId, page - 1)}
                  >
                    Anterior
                  </Button>
                  <span className="text-xs text-muted-foreground">
                    Página {page} de {Math.max(1, Math.ceil(total / 20))}
                  </span>
                  <Button
                    variant="outline"
                    disabled={page * 20 >= total || mutating}
                    onClick={() => void load(skillId, page + 1)}
                  >
                    Siguiente
                  </Button>
                </div>
              )}
            </>
          )}
        </div>
      )}
      <AlertDialog
        open={deleting !== null}
        onOpenChange={(open) => {
          if (!open && !mutating) setDeleting(null)
        }}
      >
        <AlertDialogContent
          className="max-w-[calc(100%-2rem)] sm:max-w-lg"
          onCloseAutoFocus={(event) => {
            event.preventDefault()
            if (deleteTrigger.current?.isConnected)
              deleteTrigger.current.focus()
            else addTrigger.current?.focus()
          }}
        >
          <AlertDialogHeader>
            <AlertDialogTitle>Eliminar evidencia</AlertDialogTitle>
            <AlertDialogDescription className="break-words">
              ¿Eliminar «{deleting?.title}»? Esta acción no se puede deshacer.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={mutating}>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={mutating}
              onClick={async (event) => {
                event.preventDefault()
                if (deleting && (await remove(deleting.id))) setDeleting(null)
              }}
            >
              {mutating ? <Loader2 className="animate-spin" /> : <Trash2 />}{" "}
              Confirmar eliminación
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

export function EvidenceManager({
  skill,
}: {
  skill: { id: string; skill_name: string }
}) {
  const [open, setOpen] = useState(false)
  const mutating = useSkillEvidenceStore((state) => state.mutating)
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!mutating) setOpen(next)
      }}
    >
      <DialogTrigger asChild>
        <Button variant="outline">
          <FileText /> Evidencias
        </Button>
      </DialogTrigger>
      <DialogContent
        className="flex max-h-[90dvh] max-w-[calc(100%-1.5rem)] flex-col overflow-hidden sm:max-w-2xl"
        onInteractOutside={(event) => {
          if (mutating) event.preventDefault()
        }}
        onEscapeKeyDown={(event) => {
          if (mutating) event.preventDefault()
        }}
      >
        <DialogHeader className="pr-6">
          <DialogTitle className="break-words">
            Evidencias · {skill.skill_name}
          </DialogTitle>
          <DialogDescription>
            Enlaces de respaldo aportados por ti. No certifican la habilidad ni
            sustituyen su evaluación.
          </DialogDescription>
        </DialogHeader>
        <div className="min-h-0 overflow-y-auto px-0.5 pb-1">
          {open && <EvidencePanel key={skill.id} skillId={skill.id} />}
        </div>
      </DialogContent>
    </Dialog>
  )
}

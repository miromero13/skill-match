import { useId, useState } from "react"
import { ArrowLeft, Loader2, Save } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  evidencePayload,
  evidenceTypes,
  isEvidenceType,
  validateEvidence,
  type EvidenceErrors,
  type EvidencePayload,
} from "@/types/skill-evidence"

export function EvidenceForm({
  initial,
  saving,
  onSave,
  onCancel,
}: {
  initial?: EvidencePayload
  saving: boolean
  onSave: (payload: EvidencePayload) => Promise<void>
  onCancel: () => void
}) {
  const prefix = useId()
  const [form, setForm] = useState<EvidencePayload>(
    initial ?? {
      title: "",
      description: null,
      url: "",
      evidence_type: "REPOSITORY",
    }
  )
  const [errors, setErrors] = useState<EvidenceErrors>({})
  const error = (field: keyof EvidencePayload) =>
    errors[field] ? (
      <p
        id={`${prefix}-${field}-error`}
        className="text-sm text-destructive"
        role="alert"
      >
        {errors[field]}
      </p>
    ) : null
  return (
    <form
      className="space-y-4"
      noValidate
      onSubmit={async (event) => {
        event.preventDefault()
        if (saving) return
        const nextErrors = validateEvidence(form)
        setErrors(nextErrors)
        if (Object.keys(nextErrors).length) {
          document
            .getElementById(`${prefix}-${Object.keys(nextErrors)[0]}`)
            ?.focus()
          return
        }
        await onSave(evidencePayload(form))
      }}
    >
      <Button
        type="button"
        variant="ghost"
        onClick={onCancel}
        disabled={saving}
      >
        <ArrowLeft /> Volver a evidencias
      </Button>
      <div className="space-y-2">
        <Label htmlFor={`${prefix}-title`}>Título</Label>
        <Input
          id={`${prefix}-title`}
          value={form.title}
          required
          disabled={saving}
          aria-invalid={!!errors.title}
          aria-describedby={errors.title ? `${prefix}-title-error` : undefined}
          placeholder="Por ejemplo: Proyecto de análisis de datos"
          onChange={(event) => setForm({ ...form, title: event.target.value })}
        />
        <p className="text-xs text-muted-foreground">Hasta 150 caracteres.</p>
        {error("title")}
      </div>
      <div className="space-y-2">
        <Label htmlFor={`${prefix}-evidence_type`}>Tipo de evidencia</Label>
        <Select
          value={form.evidence_type}
          disabled={saving}
          onValueChange={(value) => {
            if (isEvidenceType(value))
              setForm({ ...form, evidence_type: value })
          }}
        >
          <SelectTrigger id={`${prefix}-evidence_type`} className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {evidenceTypes.map((type) => (
              <SelectItem key={type.value} value={type.value}>
                {type.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {error("evidence_type")}
      </div>
      <div className="space-y-2">
        <Label htmlFor={`${prefix}-url`}>URL del recurso</Label>
        <Input
          id={`${prefix}-url`}
          type="url"
          inputMode="url"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          value={form.url}
          required
          disabled={saving}
          placeholder="https://github.com/usuario/proyecto"
          aria-invalid={!!errors.url}
          aria-describedby={
            errors.url ? `${prefix}-url-error` : `${prefix}-url-help`
          }
          onChange={(event) => setForm({ ...form, url: event.target.value })}
        />
        <p id={`${prefix}-url-help`} className="text-xs text-muted-foreground">
          HTTP o HTTPS, sin credenciales. Hasta 2048 caracteres.
        </p>
        {error("url")}
      </div>
      <div className="space-y-2">
        <Label htmlFor={`${prefix}-description`}>
          Descripción <span className="text-muted-foreground">(opcional)</span>
        </Label>
        <Textarea
          id={`${prefix}-description`}
          rows={3}
          value={form.description ?? ""}
          disabled={saving}
          aria-invalid={!!errors.description}
          aria-describedby={
            errors.description ? `${prefix}-description-error` : undefined
          }
          placeholder="Explica cómo respalda esta habilidad."
          onChange={(event) =>
            setForm({ ...form, description: event.target.value || null })
          }
        />
        <p className="text-xs text-muted-foreground">
          Hasta 2000 caracteres. Dejar vacío elimina la descripción.
        </p>
        {error("description")}
      </div>
      <div className="sticky bottom-0 flex flex-wrap justify-end gap-2 border-t bg-background py-3">
        <Button
          type="button"
          variant="outline"
          onClick={onCancel}
          disabled={saving}
        >
          Cancelar
        </Button>
        <Button type="submit" disabled={saving}>
          {saving ? <Loader2 className="animate-spin" /> : <Save />}{" "}
          {saving ? "Guardando…" : "Guardar evidencia"}
        </Button>
      </div>
    </form>
  )
}

import { useRef, useState, type ChangeEvent } from "react"
import { Loader2, Video } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { skillLabApi } from "../api/skill-lab-api"
import {
  formatDateTime,
  formatFileSize,
  requestFailureMessage,
  SKILL_LAB_VIDEO_ACCEPT,
} from "../lib/skill-lab-utils"
import type { SkillLabLevel, SkillLabSample } from "../types"

export const WHOLE_LEVEL = "__level__"

function describeSample(sample: SkillLabSample): string {
  return `${sample.file_format.toUpperCase()} · ${formatFileSize(sample.file_size_bytes)} · ${formatDateTime(sample.created_at)}`
}

interface ReferenceUploaderProps {
  skillId: string
  level: SkillLabLevel
  samples: SkillLabSample[]
  onChanged: () => void | Promise<void>
}

/** Video que el usuario debe replicar (S4): uno activo por nivel u opcionalmente por criterio. */
export function ReferenceUploader({ skillId, level, samples, onChanged }: ReferenceUploaderProps) {
  const [file, setFile] = useState<File | null>(null)
  const [criterionKey, setCriterionKey] = useState(WHOLE_LEVEL)
  const [consent, setConsent] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const criterionReferences = samples.filter(
    (sample) =>
      sample.sample_role === "REFERENCE" &&
      sample.skill_level_id === level.id &&
      sample.criterion_key !== null
  )
  const criterionName = (key: string | null) =>
    level.criteria.find((criterion) => criterion.key === key)?.name ?? key ?? ""

  const handleFile = (event: ChangeEvent<HTMLInputElement>) => {
    setFile(event.target.files?.[0] ?? null)
    setError(null)
  }

  const upload = async () => {
    if (!file || !consent || isUploading) return
    setIsUploading(true)
    setError(null)
    try {
      await skillLabApi.uploadSample(skillId, {
        file,
        skillLevelId: level.id,
        sampleRole: "REFERENCE",
        criterionKey: criterionKey === WHOLE_LEVEL ? null : criterionKey,
        participantId: null,
        signedConsent: true,
      })
      setFile(null)
      if (inputRef.current) inputRef.current.value = ""
      await onChanged()
    } catch (err) {
      setError(requestFailureMessage(err))
    } finally {
      setIsUploading(false)
    }
  }

  const fileId = `reference-file-${level.id}`
  const consentId = `reference-consent-${level.id}`

  return (
    <section className="space-y-3 rounded-lg border border-border/60 p-3">
      <h4 className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
        <Video className="size-4 text-emerald-500" />
        Video de referencia
      </h4>

      <div data-testid="skill-lab-reference-current" className="text-xs text-muted-foreground">
        {level.reference ? (
          <p>
            Actual: <span className="font-medium text-foreground">{describeSample(level.reference)}</span>
          </p>
        ) : (
          <p>Sin video de referencia para todo el nivel.</p>
        )}
      </div>
      {criterionReferences.length > 0 && (
        <ul className="space-y-0.5 text-xs text-muted-foreground">
          {criterionReferences.map((sample) => (
            <li key={sample.id}>
              <span className="font-medium text-foreground">{criterionName(sample.criterion_key)}</span>:{" "}
              {describeSample(sample)}
            </li>
          ))}
        </ul>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor={fileId} className="text-xs">
            Video de referencia (MP4, WebM o MOV)
          </Label>
          <Input
            ref={inputRef}
            id={fileId}
            type="file"
            accept={SKILL_LAB_VIDEO_ACCEPT}
            onChange={handleFile}
            disabled={isUploading}
            className="cursor-pointer text-xs file:cursor-pointer"
          />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Aplica a</Label>
          <Select value={criterionKey} onValueChange={setCriterionKey} disabled={isUploading}>
            <SelectTrigger aria-label="Criterio de la referencia" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={WHOLE_LEVEL}>Todo el nivel</SelectItem>
              {level.criteria.map((criterion) => (
                <SelectItem key={criterion.key} value={criterion.key}>
                  {criterion.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="flex items-start gap-2">
        <Switch id={consentId} checked={consent} onCheckedChange={setConsent} disabled={isUploading} />
        <Label htmlFor={consentId} className="text-xs leading-snug font-normal">
          Cuento con el consentimiento de la persona que aparece en el video de referencia
        </Label>
      </div>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        {file && !consent ? (
          <p className="text-xs text-amber-700 dark:text-amber-400">Activá el consentimiento para subir el video.</p>
        ) : (
          <span />
        )}
        <Button
          type="button"
          size="sm"
          onClick={upload}
          disabled={!file || !consent || isUploading}
          className="w-full sm:w-auto"
        >
          {isUploading ? <Loader2 className="animate-spin" /> : <Video />}
          {level.reference ? "Reemplazar referencia" : "Subir referencia"}
        </Button>
      </div>
      {error && <p className="text-xs text-amber-700 dark:text-amber-400">{error}</p>}
    </section>
  )
}

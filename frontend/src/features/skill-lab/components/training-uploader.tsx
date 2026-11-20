import { useRef, useState, type ChangeEvent } from "react"
import { CheckCircle2, CircleDashed, Loader2, TriangleAlert, UploadCloud } from "lucide-react"
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
import { requestFailureMessage, SKILL_LAB_VIDEO_ACCEPT } from "../lib/skill-lab-utils"
import type { SkillLabLevel } from "../types"
import { WHOLE_LEVEL } from "./reference-uploader"

type UploadStatus = "pending" | "uploading" | "done" | "error"

interface QueueItem {
  id: string
  name: string
  status: UploadStatus
  message?: string
}

const STATUS_LABEL: Record<Exclude<UploadStatus, "error">, string> = {
  pending: "En cola",
  uploading: "Subiendo…",
  done: "Subido",
}

interface TrainingUploaderProps {
  skillId: string
  level: SkillLabLevel
  onChanged: () => void | Promise<void>
}

/** Videos etiquetados por nivel y criterio para calibrar el modelo (S3). Subida secuencial. */
export function TrainingUploader({ skillId, level, onChanged }: TrainingUploaderProps) {
  const [files, setFiles] = useState<File[]>([])
  const [criterionKey, setCriterionKey] = useState(WHOLE_LEVEL)
  const [participantId, setParticipantId] = useState("")
  const [consent, setConsent] = useState(false)
  const [queue, setQueue] = useState<QueueItem[]>([])
  const [isUploading, setIsUploading] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFiles = (event: ChangeEvent<HTMLInputElement>) => {
    setFiles(Array.from(event.target.files ?? []))
  }

  const setItem = (id: string, patch: Partial<QueueItem>) =>
    setQueue((prev) => prev.map((item) => (item.id === id ? { ...item, ...patch } : item)))

  const uploadAll = async () => {
    if (files.length === 0 || !consent || isUploading) return
    const batch = files.map((file, index) => ({
      file,
      item: { id: `${Date.now()}-${index}-${file.name}`, name: file.name, status: "pending" as UploadStatus },
    }))
    setQueue(batch.map(({ item }) => item))
    setIsUploading(true)
    let uploaded = 0
    for (const { file, item } of batch) {
      setItem(item.id, { status: "uploading" })
      try {
        await skillLabApi.uploadSample(skillId, {
          file,
          skillLevelId: level.id,
          sampleRole: "TRAINING",
          criterionKey: criterionKey === WHOLE_LEVEL ? null : criterionKey,
          participantId: participantId.trim() || null,
          signedConsent: true,
        })
        uploaded += 1
        setItem(item.id, { status: "done" })
      } catch (error) {
        setItem(item.id, { status: "error", message: requestFailureMessage(error) })
      }
    }
    setIsUploading(false)
    setFiles([])
    if (inputRef.current) inputRef.current.value = ""
    if (uploaded > 0) await onChanged()
  }

  const fileId = `training-files-${level.id}`
  const participantFieldId = `training-participant-${level.id}`
  const consentId = `training-consent-${level.id}`
  const buttonLabel =
    files.length === 0 ? "Subir videos" : files.length === 1 ? "Subir 1 video" : `Subir ${files.length} videos`

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="space-y-1.5 sm:col-span-2">
          <Label htmlFor={fileId} className="text-xs">
            Videos
          </Label>
          <Input
            ref={inputRef}
            id={fileId}
            type="file"
            multiple
            accept={SKILL_LAB_VIDEO_ACCEPT}
            onChange={handleFiles}
            disabled={isUploading}
            className="cursor-pointer text-xs file:cursor-pointer"
          />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Criterio</Label>
          <Select value={criterionKey} onValueChange={setCriterionKey} disabled={isUploading}>
            <SelectTrigger aria-label="Criterio de los videos" className="w-full">
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
        <div className="space-y-1.5">
          <Label htmlFor={participantFieldId} className="text-xs">
            Participante (opcional)
          </Label>
          <Input
            id={participantFieldId}
            value={participantId}
            onChange={(event) => setParticipantId(event.target.value)}
            placeholder="Ej. P-01"
            disabled={isUploading}
          />
        </div>
      </div>

      <div className="flex items-start gap-2">
        <Switch id={consentId} checked={consent} onCheckedChange={setConsent} disabled={isUploading} />
        <Label htmlFor={consentId} className="text-xs leading-snug font-normal">
          Tengo el consentimiento de las personas de los videos
        </Label>
      </div>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        {files.length > 0 && !consent ? (
          <p className="text-xs text-amber-700 dark:text-amber-400">Activá el consentimiento.</p>
        ) : (
          <span />
        )}
        <Button
          type="button"
          size="sm"
          onClick={uploadAll}
          disabled={files.length === 0 || !consent || isUploading}
          className="w-full sm:w-auto"
        >
          {isUploading ? <Loader2 className="animate-spin" /> : <UploadCloud />}
          {buttonLabel}
        </Button>
      </div>

      {queue.length > 0 && (
        <ul className="space-y-1 rounded-md border border-border/60 p-2 text-xs" aria-label="Progreso de subida">
          {queue.map((item) => (
            <li key={item.id} className="flex flex-wrap items-center justify-between gap-2">
              <span className="min-w-0 break-all text-foreground">{item.name}</span>
              {item.status === "error" ? (
                <span className="flex items-center gap-1 text-amber-700 dark:text-amber-400">
                  <TriangleAlert className="size-3.5" />
                  {item.message}
                </span>
              ) : (
                <span
                  className={
                    item.status === "done"
                      ? "flex items-center gap-1 text-emerald-600 dark:text-emerald-400"
                      : "flex items-center gap-1 text-muted-foreground"
                  }
                >
                  {item.status === "done" ? (
                    <CheckCircle2 className="size-3.5" />
                  ) : item.status === "uploading" ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <CircleDashed className="size-3.5" />
                  )}
                  <span>{STATUS_LABEL[item.status]}</span>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

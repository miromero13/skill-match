import { useRef, useState, type ChangeEvent } from "react"
import { AlertTriangle, FileVideo, Loader2, RotateCcw, Sparkles, UploadCloud } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { MetricTypeInfo } from "@/types/catalog"
import { skillLabApi } from "../api/skill-lab-api"
import {
  formatFileSize,
  requestFailureMessage,
  SKILL_LAB_VIDEO_ACCEPT,
  WARNING_ALERT_CLASS,
} from "../lib/skill-lab-utils"
import type { SkillLabLevel, SkillValidationResult } from "../types"
import { ValidationResultView } from "./validation-result"

const AUTO_LEVEL = "__auto__"
const VALIDATION_REQUEST_FAILURE =
  "No se pudo conectar con el servidor para validar el video. Verificá la conexión e intentá de nuevo."

type ValidationState =
  | { kind: "idle" }
  | { kind: "analyzing" }
  | { kind: "result"; result: SkillValidationResult }
  | { kind: "request-failed"; message: string }

interface ValidationCardProps {
  skillId: string
  levels: SkillLabLevel[]
  metricTypes: MetricTypeInfo[]
}

/** Prueba del motor (S6): el motor nunca falla por el video; solo el transporte puede fallar. */
export function ValidationCard({ skillId, levels, metricTypes }: ValidationCardProps) {
  const [file, setFile] = useState<File | null>(null)
  const [levelId, setLevelId] = useState(AUTO_LEVEL)
  const [state, setState] = useState<ValidationState>({ kind: "idle" })
  const requestIdRef = useRef(0)
  const isAnalyzing = state.kind === "analyzing"

  const handleFile = (event: ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0] ?? null
    if (!selected) return
    requestIdRef.current += 1
    setFile(selected)
    setState({ kind: "idle" })
  }

  const runValidation = async () => {
    if (!file || isAnalyzing) return
    const requestId = ++requestIdRef.current
    setState({ kind: "analyzing" })
    try {
      const result = await skillLabApi.validate(skillId, file, levelId === AUTO_LEVEL ? null : levelId)
      if (requestId !== requestIdRef.current) return
      setState({ kind: "result", result })
    } catch (error) {
      if (requestId !== requestIdRef.current) return
      setState({ kind: "request-failed", message: requestFailureMessage(error, VALIDATION_REQUEST_FAILURE) })
    }
  }

  return (
    <Card className="border-border/60 shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-lg font-semibold">
          <FileVideo className="size-5 text-emerald-500" />
          Probar validación
        </CardTitle>
        <CardDescription>
          Subí un video para calificarlo con toda la configuración de la habilidad. Herramienta de laboratorio: no
          consume intentos ni genera una validación oficial.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 items-end gap-3 md:grid-cols-[1fr_1fr_auto]">
          <div className="space-y-1.5">
            <Label htmlFor="skill-lab-validate-file" className="text-xs">
              Video a validar (MP4, WebM o MOV)
            </Label>
            <Input
              id="skill-lab-validate-file"
              type="file"
              accept={SKILL_LAB_VIDEO_ACCEPT}
              onChange={handleFile}
              disabled={isAnalyzing}
              className="cursor-pointer text-xs file:cursor-pointer"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Nivel</Label>
            <Select value={levelId} onValueChange={setLevelId} disabled={isAnalyzing}>
              <SelectTrigger aria-label="Nivel a validar" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={AUTO_LEVEL}>Detectar nivel automáticamente</SelectItem>
                {levels.map((level) => (
                  <SelectItem key={level.id} value={level.id}>
                    {`Nivel ${level.level_number} · ${level.name}`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button type="button" onClick={runValidation} disabled={!file || isAnalyzing} className="w-full md:w-auto">
            {isAnalyzing ? (
              <>
                <Loader2 className="animate-spin" />
                Analizando…
              </>
            ) : (
              <>
                <UploadCloud />
                Validar video
              </>
            )}
          </Button>
        </div>

        {file && (
          <p className="text-xs break-all text-muted-foreground">
            Archivo seleccionado: <span className="font-medium text-foreground">{file.name}</span> (
            {formatFileSize(file.size)})
          </p>
        )}

        {isAnalyzing && (
          <div
            className="flex items-center gap-2 rounded-lg border border-border/60 bg-muted/40 p-3 text-sm text-muted-foreground"
            role="status"
          >
            <Loader2 className="size-4 shrink-0 animate-spin text-emerald-500" />
            <span>Analizando video… puede tardar unos minutos</span>
          </div>
        )}

        {state.kind === "request-failed" && (
          <Alert variant="default" className={WARNING_ALERT_CLASS} data-testid="skill-lab-validation-warning">
            <AlertTriangle />
            <AlertTitle>No se pudo completar la solicitud</AlertTitle>
            <AlertDescription className="space-y-2 text-amber-800/90 dark:text-amber-300/90">
              <p>{state.message}</p>
              <Button variant="outline" size="sm" onClick={runValidation} disabled={!file}>
                <RotateCcw />
                Reintentar
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {state.kind === "result" && (
          <>
            <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
              <Sparkles className="size-3.5" />
              Resultado de la validación
            </div>
            <ValidationResultView result={state.result} metricTypes={metricTypes} />
          </>
        )}
      </CardContent>
    </Card>
  )
}

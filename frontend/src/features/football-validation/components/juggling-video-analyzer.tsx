import { useRef, useState, type ChangeEvent } from "react"
import {
  AlertTriangle,
  CheckCircle2,
  FileVideo,
  Info,
  Loader2,
  RotateCcw,
  Sparkles,
  TrendingUp,
  UploadCloud,
} from "lucide-react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ApiError } from "@/types/api"
import {
  footballValidationApi,
  JUGGLING_VIDEO_ACCEPT,
  type JugglingLevel,
  type JugglingVideoAnalysis,
} from "../api/football-validation-api"

type AnalyzerState =
  | { kind: "idle" }
  | { kind: "analyzing" }
  | { kind: "result"; analysis: JugglingVideoAnalysis }
  | { kind: "request-failed"; message: string }

const NEUTRAL_REQUEST_FAILURE =
  "No se pudo conectar con el servidor para analizar el video. Verificá la conexión e intentá de nuevo."

const LEVEL_BADGE_CLASS: Record<JugglingLevel, string> = {
  Principiante: "border-sky-500/40 bg-sky-500/10 text-sky-600 dark:text-sky-400",
  Intermedio:
    "border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  Avanzado:
    "border-violet-500/40 bg-violet-500/10 text-violet-600 dark:text-violet-400",
  Experto:
    "border-amber-500/40 bg-amber-500/10 text-amber-600 dark:text-amber-400",
}

const WARNING_ALERT_CLASS =
  "border-amber-500/40 bg-amber-500/5 text-amber-800 dark:text-amber-300"

function requestFailureMessage(error: unknown): string {
  // statuscode 0 = fallo de red/transporte: el mensaje no proviene del APIResponse.
  if (error instanceof ApiError && error.statuscode > 0 && error.message) {
    return error.message
  }
  return NEUTRAL_REQUEST_FAILURE
}

function formatScore(score: number): string {
  return Number.isInteger(score) ? String(score) : score.toFixed(1)
}

function formatFileSize(bytes: number): string {
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function MetricTile({
  label,
  value,
  testId,
  prominent = false,
}: {
  label: string
  value: string | number
  testId: string
  prominent?: boolean
}) {
  return (
    <div
      className={
        prominent
          ? "rounded-lg border border-emerald-500/40 bg-emerald-500/5 p-3"
          : "rounded-lg border border-border/60 bg-card/40 p-3"
      }
    >
      <p className="text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
        {label}
      </p>
      <p
        data-testid={testId}
        className={
          prominent
            ? "text-3xl font-bold text-emerald-600 tabular-nums dark:text-emerald-400"
            : "text-2xl font-semibold text-foreground tabular-nums"
        }
      >
        {value}
      </p>
    </div>
  )
}

function JugglingAnalysisResult({
  analysis,
}: {
  analysis: JugglingVideoAnalysis
}) {
  return (
    <div className="space-y-4" data-testid="juggling-analysis-result">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-muted-foreground">Nivel:</span>
          <Badge
            variant="outline"
            data-testid="juggling-level-badge"
            className={`h-6 px-3 text-sm ${LEVEL_BADGE_CLASS[analysis.level] ?? ""}`}
          >
            {analysis.level}
          </Badge>
          <Badge
            variant="outline"
            className={
              analysis.ball_detected
                ? "border-emerald-500/40 text-emerald-600 dark:text-emerald-400"
                : "border-amber-500/40 text-amber-700 dark:text-amber-400"
            }
          >
            {analysis.ball_detected ? "Balón detectado: sí" : "Balón detectado: no"}
          </Badge>
        </div>
        <p
          className="text-3xl font-bold text-foreground tabular-nums"
          data-testid="juggling-score"
        >
          {formatScore(analysis.score_1_100)}
          <span className="text-base font-medium text-muted-foreground">
            /100
          </span>
        </p>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <MetricTile
          label="Mejor racha"
          value={analysis.max_streak}
          testId="juggling-max-streak"
          prominent
        />
        <MetricTile
          label="Toques totales"
          value={analysis.total_touches}
          testId="juggling-total-touches"
        />
        <MetricTile
          label="Contactos con el suelo"
          value={analysis.ground_contacts}
          testId="juggling-ground-contacts"
        />
      </div>

      <div className="space-y-1.5">
        <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
          Rachas detectadas
        </p>
        {analysis.streaks.length > 0 ? (
          <div className="flex flex-wrap gap-1.5" data-testid="juggling-streaks">
            {analysis.streaks.map((streak, index) => (
              <Badge
                key={`${index}-${streak}`}
                variant={streak === analysis.max_streak ? "default" : "secondary"}
                className="tabular-nums"
              >
                #{index + 1}: {streak}
              </Badge>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            No se registraron rachas.
          </p>
        )}
      </div>

      {analysis.notes.length > 0 && (
        <Alert
          variant="default"
          className={WARNING_ALERT_CLASS}
          data-testid="juggling-notes-alert"
        >
          <Info />
          <AlertTitle>Observaciones del análisis</AlertTitle>
          <AlertDescription className="text-amber-800/90 dark:text-amber-300/90">
            <ul className="list-disc space-y-0.5 pl-4">
              {analysis.notes.map((note, index) => (
                <li key={`${index}-${note}`}>{note}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <div className="space-y-1.5 rounded-lg border border-border/60 p-3">
          <p className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
            <CheckCircle2 className="size-4 text-emerald-500" />
            Fortalezas
          </p>
          {analysis.feedback.fortalezas.length > 0 ? (
            <ul className="list-disc space-y-0.5 pl-5 text-sm text-muted-foreground">
              {analysis.feedback.fortalezas.map((item, index) => (
                <li key={`${index}-${item}`}>{item}</li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">Sin observaciones.</p>
          )}
        </div>
        <div className="space-y-1.5 rounded-lg border border-border/60 p-3">
          <p className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
            <TrendingUp className="size-4 text-sky-500" />
            Mejoras
          </p>
          {analysis.feedback.mejoras.length > 0 ? (
            <ul className="list-disc space-y-0.5 pl-5 text-sm text-muted-foreground">
              {analysis.feedback.mejoras.map((item, index) => (
                <li key={`${index}-${item}`}>{item}</li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">Sin observaciones.</p>
          )}
        </div>
      </div>

      <p className="text-[11px] break-words text-muted-foreground">
        Detector: <span className="font-mono">{analysis.detector}</span> ·
        Modelo: <span className="font-mono">{analysis.model_version}</span> ·
        Confianza: {Math.round(analysis.confidence * 100)}% · Frames con balón:{" "}
        {analysis.ball_frames}/{analysis.frames_analyzed} · Duración:{" "}
        {analysis.duration_seconds.toFixed(1)} s
      </p>
    </div>
  )
}

export function JugglingVideoAnalyzer() {
  const [file, setFile] = useState<File | null>(null)
  const [state, setState] = useState<AnalyzerState>({ kind: "idle" })
  const requestIdRef = useRef(0)
  const isAnalyzing = state.kind === "analyzing"

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0] ?? null
    if (!selected) return
    requestIdRef.current += 1
    setFile(selected)
    setState({ kind: "idle" })
  }

  const runAnalysis = async () => {
    if (!file || isAnalyzing) return
    const requestId = ++requestIdRef.current
    setState({ kind: "analyzing" })
    try {
      const response = await footballValidationApi.analyzeJugglingVideo(file)
      if (requestId !== requestIdRef.current) return
      setState({ kind: "result", analysis: response.data })
    } catch (error) {
      if (requestId !== requestIdRef.current) return
      setState({ kind: "request-failed", message: requestFailureMessage(error) })
    }
  }

  return (
    <Card className="border-border/60 shadow-sm" data-testid="juggling-video-analyzer">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-lg font-semibold">
          <FileVideo className="size-5 text-emerald-500" />
          Analizar un video grabado
        </CardTitle>
        <CardDescription>
          Subí un video de dominadas ya grabado. Se detecta el balón, se cuentan
          los toques consecutivos (la racha se reinicia si el balón toca el
          suelo) y se asigna una calificación y un nivel. Herramienta de prueba
          para administradores: no consume intentos ni genera una validación
          oficial.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 items-end gap-3 sm:grid-cols-[1fr_auto]">
          <div className="space-y-1.5">
            <Label
              htmlFor="juggling-video-file"
              className="text-xs font-semibold tracking-wider text-muted-foreground uppercase"
            >
              Video grabado (MP4, WebM o MOV)
            </Label>
            <Input
              id="juggling-video-file"
              type="file"
              accept={JUGGLING_VIDEO_ACCEPT}
              onChange={handleFileChange}
              disabled={isAnalyzing}
              className="cursor-pointer text-xs file:cursor-pointer"
            />
          </div>
          <Button
            onClick={runAnalysis}
            disabled={!file || isAnalyzing}
            className="w-full sm:w-auto"
          >
            {isAnalyzing ? (
              <>
                <Loader2 className="animate-spin" />
                Analizando…
              </>
            ) : (
              <>
                <UploadCloud />
                Analizar video
              </>
            )}
          </Button>
        </div>

        {file && (
          <p className="text-xs break-all text-muted-foreground">
            Archivo seleccionado:{" "}
            <span className="font-medium text-foreground">{file.name}</span> (
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
          <Alert
            variant="default"
            className={WARNING_ALERT_CLASS}
            data-testid="juggling-request-warning"
          >
            <AlertTriangle />
            <AlertTitle>No se pudo completar la solicitud</AlertTitle>
            <AlertDescription className="space-y-2 text-amber-800/90 dark:text-amber-300/90">
              <p>{state.message}</p>
              <Button
                variant="outline"
                size="sm"
                onClick={runAnalysis}
                disabled={!file}
              >
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
              Resultado del análisis
            </div>
            <JugglingAnalysisResult analysis={state.analysis} />
          </>
        )}
      </CardContent>
    </Card>
  )
}

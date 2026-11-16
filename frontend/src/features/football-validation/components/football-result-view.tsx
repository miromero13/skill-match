import {
  CheckCircle2,
  ShieldAlert,
  Sparkles,
  TrendingUp,
  RotateCcw,
  FileSearch,
  Award,
  AlertCircle,
} from "lucide-react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import type { ValidationResultPayload } from "../state/football-session-machine"

export interface FootballResultViewProps {
  result: ValidationResultPayload
  retryAvailableAt?: string
  onRequestManualReview?: (sessionId: string) => void
  onRetrySession?: () => void
}

export function FootballResultView({
  result,
  retryAvailableAt,
  onRequestManualReview,
  onRetrySession,
}: FootballResultViewProps) {
  const confidencePct = Math.round(result.confianza * 100)
  const isNoBallDetected =
    result.metricas.toques === 0 ||
    result.nivel === "No calificado" ||
    result.incidencias.some((inc) => inc.tipo === "no_ball_detected")

  return (
    <div className="space-y-6 w-full" data-testid="football-result-view">
      {/* Encabezado de Nivel y Sello Verificado */}
      <Card className="border-border/80 shadow-md overflow-hidden">
        <CardHeader className="bg-secondary/30 pb-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                {isNoBallDetected ? (
                  <Badge
                    variant="destructive"
                    className="border-rose-500/50 text-rose-500 bg-rose-500/10"
                    data-testid="no-ball-badge"
                  >
                    <ShieldAlert className="w-3.5 h-3.5 mr-1" />
                    Intento No Válido (Sin Balón Detectado)
                  </Badge>
                ) : !result.requiere_revision ? (
                  <Badge
                    variant="outline"
                    className="border-emerald-500/50 text-emerald-500 bg-emerald-500/10 animate-pulse"
                    data-testid="verified-skill-seal"
                  >
                    <Award className="w-3.5 h-3.5 mr-1" />
                    Habilidad Verificada con IA Propia
                  </Badge>
                ) : (
                  <Badge
                    variant="secondary"
                    className="border-amber-500/50 text-amber-500 bg-amber-500/10"
                    data-testid="needs-review-badge"
                  >
                    <ShieldAlert className="w-3.5 h-3.5 mr-1" />
                    Pendiente de Revisión Técnica
                  </Badge>
                )}
                <Badge variant="outline" className="font-mono text-[11px]">
                  {result.version_modelo}
                </Badge>
              </div>
              <CardTitle
                className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground"
                data-testid="validated-level-title"
              >
                Nivel: {result.nivel}
              </CardTitle>
              <CardDescription className="text-xs">
                Confianza del modelo: {confidencePct}% • Coherencia Audio-Video:{" "}
                {Math.round(result.coherencia_audio_video * 100)}% • Riesgo:{" "}
                {result.puntaje_riesgo.toFixed(0)}/100
              </CardDescription>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {result.requiere_revision && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => onRequestManualReview?.(result.session_id)}
                  data-testid="request-review-button"
                >
                  <FileSearch className="w-4 h-4 mr-1.5" />
                  Solicitar Revisión
                </Button>
              )}
              <Button
                type="button"
                size="sm"
                className="bg-emerald-600 hover:bg-emerald-700 text-white"
                onClick={onRetrySession}
                data-testid="retry-session-button"
              >
                <RotateCcw className="w-4 h-4 mr-1.5" />
                {retryAvailableAt
                  ? `Reintentar (${retryAvailableAt})`
                  : "Nuevo Intento"}
              </Button>
            </div>
          </div>
        </CardHeader>

        <CardContent className="pt-5 space-y-5">
          {/* Alerta Destacada cuando no se detecta balón en movimiento */}
          {isNoBallDetected && (
            <Alert
              variant="destructive"
              className="border-rose-500/50 bg-rose-500/10 text-rose-600 dark:text-rose-400"
              data-testid="no-ball-alert"
            >
              <AlertCircle className="h-4 w-4" />
              <AlertTitle className="text-sm font-bold">
                No se detectó un balón de fútbol en movimiento
              </AlertTitle>
              <AlertDescription className="text-xs space-y-1.5 mt-1 text-foreground/90">
                <p>
                  El algoritmo de visión artificial no detectó una trayectoria activa de dominio de balón (únicamente se observó un encuadre estático o rostro).
                </p>
                <div className="text-[11px] text-muted-foreground pt-1">
                  <span className="font-semibold text-foreground">Recomendaciones para una validación válida:</span>
                  <ul className="list-disc list-inside mt-0.5 space-y-0.5">
                    <li>Coloca la cámara a 2-3 metros de distancia donde tu cuerpo completo y el suelo sean visibles.</li>
                    <li>Usa un balón de fútbol reglamentario y asegúrate de contar con buena iluminación.</li>
                    <li>Evita primeros planos del rostro o fondos con objetos esféricos en la parte superior.</li>
                  </ul>
                </div>
              </AlertDescription>
            </Alert>
          )}

          {/* Métricas Principales */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            <div className="p-3 rounded-lg bg-secondary/40 border border-border/50">
              <span className="text-[11px] text-muted-foreground block">
                Toques Totales
              </span>
              <span
                className="text-lg font-bold font-mono text-foreground"
                data-testid="metric-total-touches"
              >
                {result.metricas.toques}
              </span>
            </div>
            <div className="p-3 rounded-lg bg-secondary/40 border border-border/50">
              <span className="text-[11px] text-muted-foreground block">
                Racha Máxima
              </span>
              <span
                className="text-lg font-bold font-mono text-foreground"
                data-testid="metric-max-streak"
              >
                {result.metricas.racha}
              </span>
            </div>
            <div className="p-3 rounded-lg bg-secondary/40 border border-border/50">
              <span className="text-[11px] text-muted-foreground block">
                Toques / Min
              </span>
              <span className="text-lg font-bold font-mono text-foreground">
                {result.metricas.toques_por_minuto.toFixed(1)}
              </span>
            </div>
            <div className="p-3 rounded-lg bg-secondary/40 border border-border/50">
              <span className="text-[11px] text-muted-foreground block">
                Altura Media
              </span>
              <span className="text-lg font-bold font-mono text-foreground">
                {result.metricas.altura_media.toFixed(2)} Ø
              </span>
            </div>
            <div className="p-3 rounded-lg bg-secondary/40 border border-border/50">
              <span className="text-[11px] text-muted-foreground block">
                Regularidad
              </span>
              <span className="text-lg font-bold font-mono text-foreground">
                {Math.round(result.metricas.regularidad * 100)}%
              </span>
            </div>
          </div>

          {/* Retroalimentación Pedagógica por Plantillas */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 rounded-lg border border-emerald-500/30 bg-emerald-500/5 space-y-2">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                <Sparkles className="w-4 h-4" />
                <span>Fortalezas Detectadas</span>
              </div>
              <ul className="space-y-1.5 text-xs text-foreground list-disc list-inside">
                {result.retroalimentacion.fortalezas.map((item, idx) => (
                  <li key={idx}>{item}</li>
                ))}
              </ul>
            </div>

            <div className="p-4 rounded-lg border border-border/80 bg-secondary/20 space-y-2">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
                <TrendingUp className="w-4 h-4 text-sky-500" />
                <span>Oportunidades de Mejora</span>
              </div>
              <ul className="space-y-1.5 text-xs text-muted-foreground list-disc list-inside">
                {result.retroalimentacion.mejoras.map((item, idx) => (
                  <li key={idx}>{item}</li>
                ))}
              </ul>
            </div>
          </div>

          {/* Incidencias Antifraude (si existen) */}
          {result.incidencias.length > 0 && (
            <Alert
              variant="destructive"
              data-testid="fraud-incidents-alert"
            >
              <ShieldAlert className="h-4 w-4" />
              <AlertTitle className="text-xs font-semibold">
                Incidencias de Supervisión Registradas ({result.incidencias.length})
              </AlertTitle>
              <AlertDescription className="text-xs space-y-1 mt-1">
                {result.incidencias.map((inc, idx) => (
                  <div key={idx}>
                    • [{inc.severidad.toUpperCase()}] {inc.tipo}:{" "}
                    {inc.detalle || "Señal detectada"}
                  </div>
                ))}
              </AlertDescription>
            </Alert>
          )}

          {!result.requiere_revision && result.incidencias.length === 0 && (
            <div className="flex items-center gap-2 text-xs text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="w-4 h-4" />
              <span>
                Validación completada sin incidencias antifraude (Config:{" "}
                <code className="font-mono">{result.version_config}</code>).
              </span>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

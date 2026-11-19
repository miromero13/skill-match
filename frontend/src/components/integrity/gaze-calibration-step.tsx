import { useEffect, useRef, useState } from "react"
import { CheckCircle2, ScanEye } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import type { GazeCalibrationPoint, GazeTarget } from "@/services/browser-supervision"

/** The screen zone is calibrated by looking at the center and the four corners, in this order. */
export const GAZE_TARGETS: readonly GazeTarget[] = ["CENTER", "TOP_LEFT", "TOP_RIGHT", "BOTTOM_LEFT", "BOTTOM_RIGHT"]

const TARGET_LAYOUT: Record<GazeTarget, { left: string; top: string; instruction: string }> = {
  CENTER: { left: "50%", top: "50%", instruction: "Mirá el punto del centro de la pantalla." },
  TOP_LEFT: { left: "8%", top: "12%", instruction: "Mirá la esquina superior izquierda." },
  TOP_RIGHT: { left: "92%", top: "12%", instruction: "Mirá la esquina superior derecha." },
  BOTTOM_LEFT: { left: "8%", top: "88%", instruction: "Mirá la esquina inferior izquierda." },
  BOTTOM_RIGHT: { left: "92%", top: "88%", instruction: "Mirá la esquina inferior derecha." },
}

type Phase =
  | { name: "idle" }
  | { name: "capturing"; index: number }
  | { name: "sending" }
  | { name: "done"; message: string }
  | { name: "error"; message: string }

export interface GazeCalibrationStepProps {
  /** Returns the current camera frame as a JPEG data URL, or null while the camera is not ready. */
  captureFrame: () => string | null
  /** Sends the labelled points; resolves with the server message (shown verbatim) or rejects with its error. */
  submit: (points: GazeCalibrationPoint[]) => Promise<{ message: string }>
  /** Called once the server accepted the calibration. */
  onCalibrated?: (message: string) => void
  disabled?: boolean
  /** Frames captured per target (the server accepts 1 to 6). */
  framesPerTarget?: number
  /** Time given to move the eyes to a new target before capturing. */
  settleMs?: number
  /** Time between the frames of one target. */
  frameIntervalMs?: number
  className?: string
}

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))
const failure = (cause: unknown) => (cause instanceof Error ? cause.message : "No se pudo calibrar la mirada.")

/**
 * Guided gaze calibration: five dots (center + corners), a few frames per dot, one POST. Reusable by the
 * trial page and by the pre-exam calibration panel (S9): it only knows how to grab a frame and how to submit.
 */
export function GazeCalibrationStep({
  captureFrame,
  submit,
  onCalibrated,
  disabled = false,
  framesPerTarget = 3,
  settleMs = 1200,
  frameIntervalMs = 300,
  className,
}: GazeCalibrationStepProps) {
  const [phase, setPhase] = useState<Phase>({ name: "idle" })
  const running = useRef(false)
  const mounted = useRef(true)
  const latest = useRef({ captureFrame, submit, onCalibrated })

  useEffect(() => {
    latest.current = { captureFrame, submit, onCalibrated }
  })
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  async function run() {
    if (running.current) return
    running.current = true
    try {
      const points: GazeCalibrationPoint[] = []
      for (const [index, target] of GAZE_TARGETS.entries()) {
        if (!mounted.current) return
        setPhase({ name: "capturing", index })
        await sleep(settleMs)
        const frames: string[] = []
        for (let attempt = 0; frames.length < framesPerTarget && attempt < framesPerTarget * 4; attempt++) {
          const frame = latest.current.captureFrame()
          if (frame) frames.push(frame)
          if (frames.length < framesPerTarget) await sleep(frameIntervalMs)
        }
        if (frames.length < framesPerTarget) {
          if (mounted.current)
            setPhase({ name: "error", message: "No se pudo capturar la cámara. Verificá que esté activa y repetí la calibración." })
          return
        }
        points.push({ target, frames })
      }
      if (!mounted.current) return
      setPhase({ name: "sending" })
      const outcome = await latest.current.submit(points)
      if (!mounted.current) return
      setPhase({ name: "done", message: outcome.message })
      latest.current.onCalibrated?.(outcome.message)
    } catch (cause) {
      if (mounted.current) setPhase({ name: "error", message: failure(cause) })
    } finally {
      running.current = false
    }
  }

  const active = phase.name === "capturing" ? GAZE_TARGETS[phase.index] : null
  const progress =
    phase.name === "capturing"
      ? (phase.index / GAZE_TARGETS.length) * 100
      : phase.name === "sending" || phase.name === "done"
        ? 100
        : 0
  const busy = phase.name === "capturing" || phase.name === "sending"

  return (
    <Card className={className} data-testid="gaze-calibration">
      <CardContent className="space-y-4 p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <ScanEye className="size-5 text-emerald-600 dark:text-emerald-400" />
            <h2 className="font-semibold">Calibración de mirada</h2>
          </div>
          <Badge variant={phase.name === "done" ? "default" : "outline"} className={phase.name === "done" ? "bg-emerald-600" : ""}>
            {phase.name === "done" ? "Calibrada" : "Pendiente"}
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground">
          Para saber qué es &laquo;mirar a la pantalla&raquo; en tu equipo, mirá cada punto que se resalta: primero el
          centro y después las cuatro esquinas. Mantené la cabeza cómoda y los ojos sobre el punto; son unos segundos.
        </p>

        <div
          className="relative mx-auto aspect-video w-full max-w-md rounded-lg border bg-muted/40"
          aria-hidden={phase.name === "idle"}
        >
          {GAZE_TARGETS.map((target) => (
            <span
              key={target}
              data-testid={`gaze-dot-${target}`}
              data-active={active === target}
              className={`absolute size-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 transition-all ${
                active === target
                  ? "scale-125 border-emerald-600 bg-emerald-500 shadow-[0_0_0_6px] shadow-emerald-500/30"
                  : "border-muted-foreground/40 bg-background"
              }`}
              style={{ left: TARGET_LAYOUT[target].left, top: TARGET_LAYOUT[target].top }}
            />
          ))}
        </div>

        <Progress value={progress} aria-label="Avance de la calibración" />
        <p aria-live="polite" data-testid="gaze-calibration-status" className="min-h-5 text-sm">
          {active
            ? `Punto ${GAZE_TARGETS.indexOf(active) + 1} de ${GAZE_TARGETS.length}: ${TARGET_LAYOUT[active].instruction}`
            : phase.name === "sending"
              ? "Calculando tu zona de pantalla…"
              : phase.name === "idle"
                ? "Listo para empezar cuando quieras."
                : ""}
        </p>

        {phase.name === "done" && (
          <Alert>
            <CheckCircle2 />
            <AlertDescription>{phase.message}</AlertDescription>
          </Alert>
        )}
        {phase.name === "error" && (
          <Alert variant="destructive">
            <AlertDescription>{phase.message}</AlertDescription>
          </Alert>
        )}

        <Button onClick={() => void run()} disabled={disabled || busy} variant={phase.name === "done" ? "outline" : "default"}>
          {busy ? "Calibrando…" : phase.name === "done" ? "Calibrar de nuevo" : phase.name === "error" ? "Reintentar" : "Empezar calibración"}
        </Button>
      </CardContent>
    </Card>
  )
}

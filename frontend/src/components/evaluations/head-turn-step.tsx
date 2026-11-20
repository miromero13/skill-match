import { useEffect, useRef, useState } from "react"
import { ArrowLeft, ArrowRight, Camera, CheckCircle2 } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { captureLivenessFrames, type LivenessPhase } from "@/services/calibration-capture"
import type { CalibrationChallenge } from "@/services/evaluation-service"

export interface HeadTurnResult {
  challenge: CalibrationChallenge
  frames: string[]
}

export interface HeadTurnStepProps {
  /** Asks the server for the challenge (which side to turn to) right before capturing. */
  requestChallenge: () => Promise<CalibrationChallenge>
  /** Returns the current camera frame as a JPEG data URL, or null while the camera is not ready. */
  captureFrame: () => string | null
  onCaptured: (result: HeadTurnResult) => void
  disabled?: boolean
  className?: string
}

const PHASE_NUMBER: Record<LivenessPhase, number> = { CENTER: 1, TURN: 2, RETURN: 3 }

/** Guided head turn. The preview is mirrored, so the server's raw direction is flipped for what the member sees. */
export function HeadTurnStep({ requestChallenge, captureFrame, onCaptured, disabled = false, className }: HeadTurnStepProps) {
  const [phase, setPhase] = useState<LivenessPhase | null>(null)
  const [side, setSide] = useState<"izquierda" | "derecha" | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const controller = useRef<AbortController | null>(null)
  const mounted = useRef(true)
  const latest = useRef({ requestChallenge, captureFrame, onCaptured })

  useEffect(() => { latest.current = { requestChallenge, captureFrame, onCaptured } })
  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false; controller.current?.abort(); controller.current = null }
  }, [])

  async function run() {
    if (busy) return
    const abort = new AbortController()
    controller.current = abort
    setBusy(true); setError(null); setDone(false); setPhase(null); setSide(null)
    try {
      const challenge = await latest.current.requestChallenge()
      abort.signal.throwIfAborted()
      const requested = challenge.action === "TURN_LEFT" ? "derecha" : "izquierda"
      setSide(requested)
      const frames = await captureLivenessFrames(() => latest.current.captureFrame(), abort.signal, (next) => {
        if (mounted.current) setPhase(next)
      })
      if (!mounted.current) return
      setPhase(null); setDone(true)
      latest.current.onCaptured({ challenge, frames })
    } catch (cause) {
      if (mounted.current && !abort.signal.aborted) setError(cause instanceof Error ? cause.message : "No se pudo capturar el movimiento.")
    } finally {
      if (controller.current === abort) controller.current = null
      if (mounted.current) setBusy(false)
    }
  }

  const Arrow = side === "izquierda" ? ArrowLeft : ArrowRight
  const instruction = phase === "CENTER" ? "Mirá al centro y quedate quieto."
    : phase === "TURN" ? `Girá hacia tu ${side}.`
    : phase === "RETURN" ? "Volvé al centro y quedate quieto." : ""
  return (
    <Card className={className} data-testid="head-turn">
      <CardContent className="space-y-3 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            {phase === "TURN" && side ? <Arrow className="size-6 text-primary" aria-hidden="true" /> : <Camera className="size-5 text-primary" aria-hidden="true" />}
            <h2 className="font-semibold">Giro de cabeza</h2>
          </div>
          <Badge variant={done ? "default" : "outline"} className={done ? "bg-emerald-600" : ""}>{done ? "Capturado" : "Pendiente"}</Badge>
        </div>
        {!phase && !done && (
          <p className="text-sm text-muted-foreground">
            Mirá al frente, girá la cabeza al lado indicado y volvé al centro (~12 s).
          </p>
        )}
        {phase === "TURN" && side && (
          <div className="flex items-center justify-center gap-2 rounded-lg border border-primary/30 bg-primary/5 p-3 text-base font-semibold text-primary">
            <Arrow className="size-6 shrink-0" aria-hidden="true" />
            <span>Girá hacia tu {side}</span>
          </div>
        )}
        <Progress value={phase ? (PHASE_NUMBER[phase] / 3) * 100 : done ? 100 : 0} aria-label="Avance del giro de cabeza" />
        <p aria-live="polite" data-testid="head-turn-status" className="min-h-5 text-sm font-medium">
          {phase ? `Paso ${PHASE_NUMBER[phase]} de 3 · ${instruction}` : busy ? "Preparando el movimiento…" : "Presioná el botón cuando estés listo."}
        </p>
        {done && <Alert><CheckCircle2 /><AlertDescription>Movimiento capturado.</AlertDescription></Alert>}
        {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
        <Button onClick={() => void run()} disabled={disabled || busy} variant={done ? "outline" : "default"} className="w-full sm:w-auto">
          {busy ? "Capturando…" : error ? "Reintentar" : "Empezar giro de cabeza"}
        </Button>
      </CardContent>
    </Card>
  )
}

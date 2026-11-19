import { useEffect, useRef, useState } from "react"
import { CheckCircle2, Mic } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import type { VoiceCalibrationRequest } from "@/services/browser-supervision"
import type { MouthSampleDTO } from "@/services/gaze-tracking"

/** The control phrase the candidate reads aloud: long enough for several seconds of continuous speech. */
export const VOICE_PHRASE = "Hoy rindo esta prueba yo solo, y mi voz es la que se escucha en este micrófono."

/** Captures 16 kHz mono audio between `start()` and `stop()`; `startedAt` is the epoch ms of the first sample. */
export interface VoiceRecorder {
  start: () => void
  stop: () => { samples: number[]; startedAt: number } | null
}

type Phase =
  | { name: "idle" }
  | { name: "silence"; remainingMs: number }
  | { name: "reading"; remainingMs: number }
  | { name: "sending" }
  | { name: "done"; message: string }
  | { name: "error"; message: string }

export interface VoiceCalibrationStepProps {
  recorder: VoiceRecorder
  /** Mouth-aperture readings of [startedAt, startedAt + durationMs], as offsets from `startedAt`. */
  readMouth: (startedAt: number, durationMs: number) => MouthSampleDTO[]
  /** Sends the recording; resolves with the server message (shown verbatim) or rejects with its error. */
  submit: (request: VoiceCalibrationRequest) => Promise<{ message: string }>
  /** Called once the server accepted the voiceprint. */
  onCalibrated?: (message: string) => void
  disabled?: boolean
  /** Silence before the phrase; the server measures the ambient noise floor from it (500-3000 ms). */
  ambientMs?: number
  /** Time given to read the phrase aloud. */
  phraseMs?: number
  /** Refresh interval of the countdown. */
  tickMs?: number
  phrase?: string
  className?: string
}

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))
const seconds = (ms: number) => Math.max(1, Math.ceil(ms / 1000))
const failure = (cause: unknown) => (cause instanceof Error ? cause.message : "No se pudo calibrar la voz.")
const CAPTURE_ERROR = "No se pudo capturar el micrófono. Verificá que esté activo y repetí la calibración."

/**
 * Guided voice calibration: a short silence (ambient noise floor), then a control phrase read aloud while the
 * microphone and the mouth are recorded, one POST. Reusable by the trial page and by the pre-exam calibration
 * panel (S9): it only knows how to record, read the mouth readings and submit.
 */
export function VoiceCalibrationStep({
  recorder,
  readMouth,
  submit,
  onCalibrated,
  disabled = false,
  ambientMs = 2000,
  phraseMs = 7000,
  tickMs = 250,
  phrase = VOICE_PHRASE,
  className,
}: VoiceCalibrationStepProps) {
  const [phase, setPhase] = useState<Phase>({ name: "idle" })
  const running = useRef(false)
  const mounted = useRef(true)
  const latest = useRef({ recorder, readMouth, submit, onCalibrated })

  useEffect(() => {
    latest.current = { recorder, readMouth, submit, onCalibrated }
  })
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  async function countdown(total: number, name: "silence" | "reading") {
    for (let left = total; left > 0 && mounted.current; left -= tickMs) {
      setPhase(name === "silence" ? { name: "silence", remainingMs: left } : { name: "reading", remainingMs: left })
      await sleep(Math.min(tickMs, left))
    }
  }

  async function run() {
    if (running.current) return
    running.current = true
    let recording = false
    try {
      latest.current.recorder.start()
      recording = true
      await countdown(ambientMs, "silence")
      await countdown(phraseMs, "reading")
      recording = false
      const captured = latest.current.recorder.stop()
      if (!mounted.current) return
      if (!captured || captured.samples.length === 0) {
        setPhase({ name: "error", message: CAPTURE_ERROR })
        return
      }
      setPhase({ name: "sending" })
      const outcome = await latest.current.submit({
        audio_samples: captured.samples,
        ambient_ms: ambientMs,
        mouth_samples: latest.current.readMouth(captured.startedAt, ambientMs + phraseMs),
      })
      if (!mounted.current) return
      setPhase({ name: "done", message: outcome.message })
      latest.current.onCalibrated?.(outcome.message)
    } catch (cause) {
      if (mounted.current) setPhase({ name: "error", message: failure(cause) })
    } finally {
      if (recording) latest.current.recorder.stop() // leaving midway never leaves the microphone buffer filling up
      running.current = false
    }
  }

  const busy = phase.name === "silence" || phase.name === "reading" || phase.name === "sending"
  const progress =
    phase.name === "silence"
      ? ((ambientMs - phase.remainingMs) / (ambientMs + phraseMs)) * 100
      : phase.name === "reading"
        ? ((ambientMs + phraseMs - phase.remainingMs) / (ambientMs + phraseMs)) * 100
        : phase.name === "sending" || phase.name === "done"
          ? 100
          : 0

  return (
    <Card className={className} data-testid="voice-calibration">
      <CardContent className="space-y-4 p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Mic className="size-5 text-emerald-600 dark:text-emerald-400" />
            <h2 className="font-semibold">Calibración de voz</h2>
          </div>
          <Badge variant={phase.name === "done" ? "default" : "outline"} className={phase.name === "done" ? "bg-emerald-600" : ""}>
            {phase.name === "done" ? "Calibrada" : "Pendiente"}
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground">
          Para confirmar que la voz de la prueba es la tuya, primero quedate unos segundos en silencio y después leé en
          voz alta la frase que aparece, mirando a la cámara. Tiene que hablar solo vos, sin música ni audio reproducido.
        </p>

        {phase.name === "reading" && (
          <p
            data-testid="voice-phrase"
            className="rounded-lg border bg-muted/40 p-4 text-center text-lg font-medium leading-snug"
          >
            {phrase}
          </p>
        )}

        <Progress value={progress} aria-label="Avance de la calibración de voz" />
        <p aria-live="polite" data-testid="voice-calibration-status" className="min-h-5 text-sm">
          {phase.name === "silence"
            ? `Quedate en silencio: ${seconds(phase.remainingMs)} s`
            : phase.name === "reading"
              ? `Leé en voz alta la frase: ${seconds(phase.remainingMs)} s`
              : phase.name === "sending"
                ? "Registrando tu voz…"
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
          {busy
            ? "Calibrando…"
            : phase.name === "done"
              ? "Calibrar de nuevo"
              : phase.name === "error"
                ? "Reintentar"
                : "Empezar calibración de voz"}
        </Button>
      </CardContent>
    </Card>
  )
}

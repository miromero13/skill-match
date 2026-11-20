import { useEffect, useRef, useState } from "react"
import { CheckCircle2, Mic } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { assembleVoiceRequest, createFrameSampler, VOICE_FRAME_INTERVAL_MS, type FrameSampler, type VoiceRecorder } from "@/services/av-capture"
import type { VoiceCalibrationRequest } from "@/services/browser-supervision"
import type { MouthSampleDTO } from "@/services/gaze-tracking"

export type { VoiceRecorder }

/** The control phrase the candidate reads aloud: long enough for several seconds of continuous speech. */
export const VOICE_PHRASE = "Hoy rindo esta prueba yo solo, y mi voz es la que se escucha en este micrófono."

type Phase =
  | { name: "idle" }
  | { name: "silence"; remainingMs: number }
  | { name: "reading"; remainingMs: number }
  | { name: "pause"; remainingMs: number }
  | { name: "sending" }
  | { name: "done"; message: string }
  | { name: "error"; message: string }

export interface VoiceCalibrationStepProps {
  recorder: VoiceRecorder
  /** Returns the current camera frame as a JPEG data URL (at most 80000 chars), or null while the camera is not ready. */
  captureFrame: () => string | null
  /** Mouth-aperture readings of [startedAt, startedAt + durationMs], as offsets from `startedAt`. */
  readMouth: (startedAt: number, durationMs: number) => MouthSampleDTO[]
  /** Sends the recording; resolves with the server message (shown verbatim) or rejects with its error. */
  submit: (request: VoiceCalibrationRequest) => Promise<{ message: string }>
  /** Called once the server accepted the voiceprint. */
  onCalibrated?: (message: string) => void
  disabled?: boolean
  /** Starts the recording as soon as the step is shown (no click), for flows bound by a server deadline. */
  autoStart?: boolean
  /** Silence before the phrase; the server measures the ambient noise floor from it (500-3000 ms). */
  ambientMs?: number
  /** Time given to read the phrase aloud. */
  phraseMs?: number
  /** Silent pause after the phrase (nothing may be said or mouthed); 0 means the phrase runs to the end. */
  pauseMs?: number
  /** Time between the sampled server frames (they are required by the server and measured on the same clock). */
  frameIntervalMs?: number
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
  captureFrame,
  submit,
  onCalibrated,
  disabled = false,
  autoStart = false,
  ambientMs = 2000,
  phraseMs = 7000,
  pauseMs = 0,
  frameIntervalMs = VOICE_FRAME_INTERVAL_MS,
  tickMs = 250,
  phrase = VOICE_PHRASE,
  className,
}: VoiceCalibrationStepProps) {
  const [phase, setPhase] = useState<Phase>({ name: "idle" })
  const running = useRef(false)
  const mounted = useRef(true)
  const sampler = useRef<FrameSampler | null>(null)
  const latest = useRef({ recorder, readMouth, captureFrame, submit, onCalibrated })

  const session = useRef(0)

  useEffect(() => {
    latest.current = { recorder, readMouth, captureFrame, submit, onCalibrated }
  })
  useEffect(() => {
    mounted.current = true
    return () => {
      // Unmount (also the simulated one of StrictMode): the running capture is abandoned for good. Without bumping
      // `session` the old run would resume on the remount with its frame sampler already disposed, and send one frame.
      mounted.current = false
      session.current++
      if (running.current) latest.current.recorder.stop()
      sampler.current?.dispose()
      sampler.current = null
      running.current = false
    }
  }, [])

  async function countdown(total: number, name: "silence" | "reading" | "pause", stale: () => boolean) {
    for (let left = total; left > 0 && !stale(); left -= tickMs) {
      setPhase(
        name === "silence"
          ? { name: "silence", remainingMs: left }
          : name === "reading"
            ? { name: "reading", remainingMs: left }
            : { name: "pause", remainingMs: left },
      )
      await sleep(Math.min(tickMs, left))
    }
  }

  async function run() {
    if (running.current) return
    running.current = true
    const mine = ++session.current
    const stale = () => !mounted.current || session.current !== mine
    const own = createFrameSampler(() => latest.current.captureFrame(), frameIntervalMs)
    let recording = false
    try {
      latest.current.recorder.start()
      recording = true
      sampler.current = own
      own.start()
      await countdown(ambientMs, "silence", stale)
      await countdown(phraseMs, "reading", stale)
      if (pauseMs > 0) await countdown(pauseMs, "pause", stale)
      if (stale()) return // the finally block stops the frame timer
      recording = false
      const captured = latest.current.recorder.stop()
      const frames = own.stop()
      if (stale()) return
      if (!captured || captured.samples.length === 0) {
        setPhase({ name: "error", message: CAPTURE_ERROR })
        return
      }
      setPhase({ name: "sending" })
      const outcome = await latest.current.submit(
        assembleVoiceRequest(
          captured,
          frames,
          latest.current.readMouth(captured.startedAt, ambientMs + phraseMs + pauseMs),
          ambientMs,
        ),
      )
      if (stale()) return
      setPhase({ name: "done", message: outcome.message })
      latest.current.onCalibrated?.(outcome.message)
    } catch (cause) {
      if (!stale()) setPhase({ name: "error", message: failure(cause) })
    } finally {
      // A stale run never touches the recorder or the flags: the unmount cleanup already released them and a newer
      // run may own them now.
      if (recording && !stale()) latest.current.recorder.stop() // leaving midway never leaves the microphone filling up
      own.dispose()
      if (sampler.current === own) sampler.current = null
      if (session.current === mine) running.current = false
    }
  }

  const runner = useRef(run)
  useEffect(() => {
    runner.current = run
  })
  useEffect(() => {
    if (autoStart) void runner.current()
  }, [autoStart])

  const busy = phase.name === "silence" || phase.name === "reading" || phase.name === "pause" || phase.name === "sending"
  const totalMs = ambientMs + phraseMs + pauseMs
  const elapsedBefore = { silence: 0, reading: ambientMs, pause: ambientMs + phraseMs }
  const length = { silence: ambientMs, reading: phraseMs, pause: pauseMs }
  const progress =
    phase.name === "silence" || phase.name === "reading" || phase.name === "pause"
      ? ((elapsedBefore[phase.name] + length[phase.name] - phase.remainingMs) / totalMs) * 100
      : phase.name === "sending" || phase.name === "done"
        ? 100
        : 0

  return (
    <Card className={className} data-testid="voice-calibration">
      <CardContent className="space-y-3 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Mic className="size-5 text-emerald-600 dark:text-emerald-400" />
            <h2 className="font-semibold">Calibración de voz</h2>
          </div>
          <Badge variant={phase.name === "done" ? "default" : "outline"} className={phase.name === "done" ? "bg-emerald-600" : ""}>
            {phase.name === "done" ? "Calibrada" : "Pendiente"}
          </Badge>
        </div>
        {(phase.name === "idle" || phase.name === "error") && (
          <p className="text-sm text-muted-foreground">
            Primero guardá silencio, luego leé la frase en pantalla y terminá en silencio.
          </p>
        )}

        {phase.name === "silence" && (
          <div className="rounded-lg border border-amber-200 bg-amber-50/70 p-3 text-center text-sm font-medium text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-200">
            🤫 Silencio total por unos segundos. No hables todavía.
          </div>
        )}

        {phase.name === "reading" && (
          <p
            data-testid="voice-phrase"
            className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3.5 text-center text-base font-semibold leading-snug"
          >
            {phrase}
          </p>
        )}

        {phase.name === "pause" && (
          <div className="rounded-lg border border-amber-200 bg-amber-50/70 p-3 text-center text-sm font-medium text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-200">
            🤫 Ya terminaste. No hables ni muevas los labios.
          </div>
        )}

        <Progress value={progress} aria-label="Avance de la calibración de voz" />
        <p aria-live="polite" data-testid="voice-calibration-status" className="min-h-5 text-sm font-medium">
          {phase.name === "silence"
            ? `Quedate en silencio: ${seconds(phase.remainingMs)} s`
            : phase.name === "reading"
              ? `Leé en voz alta la frase: ${seconds(phase.remainingMs)} s`
              : phase.name === "pause"
                ? `No hables ni muevas la boca: ${seconds(phase.remainingMs)} s`
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

        {(!autoStart || phase.name === "error" || phase.name === "done") && (
          <Button onClick={() => void run()} disabled={disabled || busy} variant={phase.name === "done" ? "outline" : "default"} className="w-full sm:w-auto">
            {busy
              ? "Calibrando…"
              : phase.name === "done"
                ? "Calibrar de nuevo"
                : phase.name === "error"
                  ? "Reintentar"
                  : "Empezar calibración de voz"}
          </Button>
        )}
      </CardContent>
    </Card>
  )
}

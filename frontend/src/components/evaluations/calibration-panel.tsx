import { useCallback, useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Card, CardContent } from "@/components/ui/card"
import { ArrowLeft, ArrowRight, Camera, CheckCircle2 } from "lucide-react"
import { CalibrationChecks } from "@/components/evaluations/calibration-checks"
import { HeadTurnStep, type HeadTurnResult } from "@/components/evaluations/head-turn-step"
import { GazeCalibrationStep } from "@/components/integrity/gaze-calibration-step"
import { VoiceCalibrationStep } from "@/components/integrity/voice-calibration-step"
import { createMicrophoneRecorder, type MicrophoneRecorder } from "@/services/av-capture"
import type { GazeCalibrationPoint, VoiceCalibrationRequest } from "@/services/browser-supervision"
import { buildCalibrationEvidence } from "@/services/calibration-capture"
import { requestCalibrationChallenge, verifyEvaluationCalibration, type CalibrationState } from "@/services/evaluation-service"
import { startFaceTracker, type FaceTracker } from "@/services/gaze-tracking"
import { ApiError } from "@/types/api"

/** Short enough to be read before second 4.5 of the speech segment, after which nothing may be said. */
const CALIBRATION_PHRASE = "Hoy rindo esta prueba yo solo, y mi voz es la que se escucha."
const STEPS = ["Mirada", "Giro de cabeza", "Silencio y frase", "Verificación"] as const
/** The server issues a liveness challenge for 45 s (backend `evaluation_calibration_service`). */
const CHALLENGE_TTL_MS = 45_000
/** Silence (3 s) + phrase (4 s) + pause (4 s) of the voice step, plus time to send and verify. */
const VOICE_STEP_MS = 11_000
const VERIFY_MARGIN_MS = 4_000
const EXPIRED_MESSAGE =
  "El reto del giro de cabeza venció (dura 45 segundos). Tu mirada ya está lista: repetí el giro de cabeza y la frase. No se descontó tu intento."
const MIN_WIDTH = 320
const MIN_HEIGHT = 240

interface Devices { recorder: MicrophoneRecorder; tracker: FaceTracker }

export function CalibrationPanel({ evaluationId, onBack }: { evaluationId: string; onBack?: () => void }) {
  const video = useRef<HTMLVideoElement>(null)
  const canvas = useRef<HTMLCanvasElement | null>(null)
  const stream = useRef<MediaStream | null>(null)
  const recorderRef = useRef<MicrophoneRecorder | null>(null)
  const trackerRef = useRef<FaceTracker | null>(null)
  const cameraLabel = useRef("")
  const alive = useRef(false)
  const generation = useRef(0)
  const challengeDeadline = useRef(0)
  const [devices, setDevices] = useState<Devices | null>(null)
  const [videoReady, setVideoReady] = useState(false)
  const [busy, setBusy] = useState(false)
  const [verifying, setVerifying] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [round, setRound] = useState(0)
  const [gaze, setGaze] = useState<GazeCalibrationPoint[] | null>(null)
  const [movement, setMovement] = useState<HeadTurnResult | null>(null)
  const [voice, setVoice] = useState<VoiceCalibrationRequest | null>(null)
  const [result, setResult] = useState<CalibrationState | null>(null)

  const release = useCallback(() => {
    stream.current?.getTracks().forEach(track => track.stop())
    stream.current = null
    trackerRef.current?.stop()
    trackerRef.current = null
    if (recorderRef.current) void recorderRef.current.close().catch(() => undefined)
    recorderRef.current = null
    if (video.current) video.current.srcObject = null
  }, [])

  const invalidate = useCallback(() => { generation.current++ }, [])
  useEffect(() => {
    alive.current = true
    return () => { alive.current = false; invalidate(); release() }
  }, [evaluationId, release, invalidate])

  /** Drops the head turn and the voice take (their challenge is gone) but keeps the completed gaze step. */
  function restartFromChallenge(text: string) {
    setMovement(null); setVoice(null); setResult(null); setVerifying(false); setError(text)
    setRound(value => value + 1)
  }

  /** Remembers when the challenge dies: 45 s from receipt, or the server's own `expires_at` if that is sooner. */
  async function issueChallenge() {
    const challenge = await requestCalibrationChallenge(evaluationId)
    const remaining = Date.parse(challenge.expires_at) - Date.now()
    challengeDeadline.current = Date.now() + (remaining > 0 ? Math.min(CHALLENGE_TTL_MS, remaining) : CHALLENGE_TTL_MS)
    return challenge
  }

  function headTurnCaptured(captured: HeadTurnResult) {
    if (challengeDeadline.current - Date.now() < VOICE_STEP_MS + VERIFY_MARGIN_MS) { restartFromChallenge(EXPIRED_MESSAGE); return }
    setMovement(captured)
  }

  function resetEvidence() {
    setGaze(null); setMovement(null); setVoice(null); setResult(null); setError(null); setRound(value => value + 1)
  }

  /** One JPEG of the camera in its original orientation (CSS mirrors only the preview), at most `maxWidth` wide. */
  function grab(maxWidth: number, quality: number): string | null {
    const source = video.current
    if (!source || !source.videoWidth || !source.videoHeight) return null
    const target = canvas.current ??= document.createElement("canvas")
    target.width = Math.min(maxWidth, source.videoWidth)
    target.height = Math.round(source.videoHeight * target.width / source.videoWidth)
    const context = target.getContext("2d")
    if (!context) return null
    context.drawImage(source, 0, 0, target.width, target.height)
    return target.toDataURL("image/jpeg", quality)
  }

  async function prepare() {
    const current = ++generation.current
    setBusy(true); resetEvidence(); setVideoReady(false)
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("Camera access unavailable")
      const media = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640, max: 1280 }, height: { ideal: 480, max: 960 }, facingMode: "user" },
        audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
      })
      if (!alive.current || current !== generation.current) { media.getTracks().forEach(track => track.stop()); return }
      stream.current = media
      const camera = media.getVideoTracks()[0]
      if (!camera || camera.readyState !== "live" || media.getAudioTracks()[0]?.readyState !== "live") {
        throw new Error("Camera or microphone unavailable")
      }
      const known = await navigator.mediaDevices.enumerateDevices()
      cameraLabel.current = known.find(device => device.deviceId === camera.getSettings().deviceId)?.label || camera.label
      const recorder = await createMicrophoneRecorder(media)
      recorderRef.current = recorder
      if (!alive.current || current !== generation.current) { release(); return }
      if (video.current) video.current.srcObject = media
      let tracker: FaceTracker
      try {
        tracker = await startFaceTracker(video.current!)
      } catch {
        release()
        if (alive.current && current === generation.current) {
          setError("No se pudo iniciar el análisis del rostro en el navegador. Recargá la página y repetí la calibración.")
        }
        return
      }
      trackerRef.current = tracker
      if (!alive.current || current !== generation.current) { release(); return }
      setDevices({ recorder, tracker })
    } catch {
      release()
      if (alive.current && current === generation.current) {
        setDevices(null)
        setError("No se pudo acceder a la cámara o al micrófono. Revisá los permisos y usá una conexión segura o localhost.")
      }
    } finally {
      if (alive.current && current === generation.current) setBusy(false)
    }
  }

  function closeDevices() {
    generation.current++
    release(); setDevices(null); setVideoReady(false); setBusy(false); setVerifying(false); resetEvidence()
  }

  function cameraLoaded() {
    const source = video.current
    if (source && (source.videoWidth < MIN_WIDTH || source.videoHeight < MIN_HEIGHT)) {
      closeDevices()
      setError(`La cámara no entrega la resolución mínima de ${MIN_WIDTH}×${MIN_HEIGHT} para la calibración.`)
      return
    }
    setVideoReady(true)
  }

  async function verify(recording: VoiceCalibrationRequest) {
    if (!gaze || !movement) return
    if (challengeDeadline.current - Date.now() < 1_500) { restartFromChallenge(EXPIRED_MESSAGE); return }
    const current = ++generation.current
    setVerifying(true); setError(null)
    try {
      const evidence = buildCalibrationEvidence({
        challengeId: movement.challenge.id, frames: movement.frames, gazePoints: gaze, voice: recording,
        cameraLabel: cameraLabel.current,
      })
      const state = await verifyEvaluationCalibration(evaluationId, evidence)
      if (!alive.current || current !== generation.current) return
      setResult(state)
      if (state.ready && Object.values(state.checks).every(Boolean)) { release(); setDevices(null); setVideoReady(false) }
    } catch (cause) {
      if (alive.current && current === generation.current) {
        const text = cause instanceof Error ? cause.message : "No se pudo completar la calibración."
        if (cause instanceof ApiError && cause.statuscode === 410) restartFromChallenge(text) // the server's own message
        else setError(text)
      }
    } finally {
      if (alive.current && current === generation.current) setVerifying(false)
    }
  }

  const passed = !!result?.ready && Object.values(result.checks).every(Boolean)
  const stepIndex = !gaze ? 0 : !movement ? 1 : !voice ? 2 : 3
  const stepsDisabled = !devices || !videoReady

  return <section aria-label="Comprobación del ambiente" className="space-y-4">
    <Card className="rounded-xl border bg-muted/20 py-0 shadow-none ring-0">
      <CardContent className="gap-4 p-4 sm:p-5">
        <h2 className="text-xs leading-relaxed font-bold text-primary uppercase">Paso 3 de 3: calibración de cámara y micrófono</h2>
        <div className="grid items-center gap-5 sm:grid-cols-[minmax(0,280px)_minmax(0,1fr)]">
          <div className="relative flex aspect-video min-w-0 items-center justify-center overflow-hidden rounded-lg bg-zinc-900">
            <video ref={video} autoPlay muted playsInline onLoadedData={cameraLoaded}
              className={`absolute inset-0 size-full -scale-x-100 object-contain ${devices ? "opacity-100" : "opacity-0"}`} aria-label="Vista previa de cámara" />
            <div className="pointer-events-none relative mb-5 h-24 w-[72px] rounded-[48%] border-2 border-primary" aria-hidden="true">
              {!devices && <Camera className="absolute inset-0 m-auto size-5 text-primary" />}
            </div>
            <p className="absolute inset-x-2 bottom-3 text-center text-[11px] font-medium text-emerald-400">{passed ? "Captura finalizada · cámara apagada" : devices ? "Mantené tu rostro dentro de la guía" : "Cámara apagada · esperá para dar permiso"}</p>
          </div>
          <div className="min-w-0 space-y-3">
            <ol aria-label="Pasos de la calibración" className="grid grid-cols-2 gap-2 text-center text-xs">
              {STEPS.map((label, index) => <li key={label} aria-current={!passed && stepIndex === index ? "step" : undefined}
                className={`rounded-lg border px-2 py-2 ${passed || index < stepIndex ? "border-emerald-500/40 text-emerald-700 dark:text-emerald-400" : stepIndex === index ? "border-primary bg-primary text-primary-foreground" : "text-muted-foreground"}`}>
                {index + 1}. {label}
              </li>)}
            </ol>
            <p className="text-xs leading-relaxed text-muted-foreground">{devices ? "Cámara y micrófono preparados. Seguí los pasos en orden: mirada, giro de cabeza, silencio y frase. Al terminar se verifica todo junto." : "La cámara y el micrófono están apagados. Los permisos se solicitan solo cuando lo indicás. Prepará buena iluminación, rostro centrado y una sola persona visible."}</p>
          </div>
        </div>
        {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
      </CardContent>
    </Card>
    {!passed && devices && !result && <>
      {!gaze && <GazeCalibrationStep key={`gaze-${round}`} disabled={stepsDisabled} captureFrame={() => grab(640, .65)}
        submit={async points => { setGaze(points); return { message: "Puntos de mirada capturados." } }} />}
      {gaze && !movement && <HeadTurnStep key={`turn-${round}`} disabled={stepsDisabled} captureFrame={() => grab(640, .65)}
        requestChallenge={issueChallenge} onCaptured={headTurnCaptured} />}
      {gaze && movement && !voice && <VoiceCalibrationStep key={`voice-${round}`} disabled={stepsDisabled} autoStart recorder={devices.recorder}
        captureFrame={() => grab(480, .55)} readMouth={(startedAt, durationMs) => devices.tracker.takeMouthSamples(startedAt, durationMs)}
        ambientMs={3000} phraseMs={4000} pauseMs={4000} phrase={CALIBRATION_PHRASE}
        submit={async recording => { setVoice(recording); void verify(recording); return { message: "Captura de voz lista. Verificando…" } }} />}
      {voice && verifying && <p role="status" className="text-sm font-medium">Verificando tu calibración… Ya podés quedarte quieto.</p>}
    </>}
    {result && <Card className="rounded-xl border py-0 shadow-none ring-0"><CardContent className="space-y-3 p-4 sm:p-5">
      {passed ? <div className="flex items-start gap-2 text-sm text-emerald-700 dark:text-emerald-400">
        <CheckCircle2 className="size-5 shrink-0" aria-hidden="true" /><div><p className="font-semibold">Comprobación superada</p><p className="mt-1 text-xs">Mirada, movimiento, ambiente sonoro, voz e identidad comprobados en esta captura.</p></div>
      </div> : <Alert variant="destructive"><AlertDescription>La calibración no se completó. Revisá los controles marcados y repetí la captura.</AlertDescription></Alert>}
      <CalibrationChecks checks={result.checks} />
      {passed && <p className="text-xs leading-relaxed text-muted-foreground">El examen no comenzó y tu intento no se descontó. Continuá a la pantalla oral para revisar los requisitos antes de confirmar el inicio. La supervisión continua aún no está conectada.</p>}
    </CardContent></Card>}
    {!passed && <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
      {!devices && <Button className="h-auto min-h-11 whitespace-normal py-2" disabled={busy} onClick={() => void prepare()}>Preparar cámara y micrófono</Button>}
      {(error || result) && devices && !verifying && <Button className="h-auto min-h-11 whitespace-normal py-2" onClick={resetEvidence}>Repetir calibración</Button>}
      {devices && <Button variant="outline" className="h-auto min-h-11 whitespace-normal py-2" onClick={closeDevices}>Cerrar cámara y micrófono</Button>}
    </div>}
    {!passed && <p className="text-xs leading-relaxed text-muted-foreground">La captura guiada dura unos 45 segundos: 10 de mirada, 12 de giro de cabeza y 11 de silencio y frase. El reto del giro vence a los 45 segundos. Se estiman varios hablantes, superposición y coincidencia entre boca y audio. No se identifica quién habla; estos controles no garantizan detectar toda llamada, pantalla o video manipulado. Podés repetir sin gastar el intento.</p>}
    <div className="flex flex-col-reverse justify-between gap-3 sm:flex-row">
      {onBack && <Button variant="outline" className="h-11" onClick={onBack}><ArrowLeft aria-hidden="true" />Volver a Normas</Button>}
      {passed
        ? <Button asChild className="h-11 sm:ml-auto sm:px-6"><a href={`/evaluation/${evaluationId}/theory`}>Continuar al examen oral<ArrowRight aria-hidden="true" /></a></Button>
        : <Button disabled className="h-11 sm:ml-auto sm:px-6" title="Completá primero la calibración">Comenzar primera prueba<ArrowRight aria-hidden="true" /></Button>}
    </div>
  </section>
}

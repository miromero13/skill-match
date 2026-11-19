import { useCallback, useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { ArrowLeft, ArrowRight, Camera, CheckCircle2, Mic } from "lucide-react"
import {
  requestCalibrationChallenge, verifyEvaluationCalibration, type CalibrationState,
} from "@/services/evaluation-service"
import {
  captureCalibrationEvidence, createMicrophoneMonitor, type MicrophoneMonitor, type CalibrationCapturePhase,
} from "@/services/calibration-capture"

const labels: Record<string, string> = {
  lighting: "Iluminación", framing: "Encuadre", single_face: "Una sola persona visible",
  microphone: "Actividad de voz detectada", background_quiet: "Fondo sin voz detectada durante el silencio", identity: "Coincidencia con el rostro enrolado",
  single_speaker: "Estimación de una sola voz", no_overlap: "Sin voces superpuestas detectadas",
  mouth_audio_sync: "Movimiento de boca coincidente con voz", speech_pause: "Pausa sin voz detectada",
  liveness: "Movimiento solicitado", passive_screen_check: "Sin patrones de pantalla evidentes (heurística)",
}

export function CalibrationPanel({ evaluationId, onBack }: { evaluationId: string; onBack?: () => void }) {
  const video = useRef<HTMLVideoElement>(null)
  const stream = useRef<MediaStream | null>(null)
  const microphone = useRef<MicrophoneMonitor | null>(null)
  const cameraLabel = useRef("")
  const controller = useRef<AbortController | null>(null)
  const alive = useRef(false)
  const generation = useRef(0)
  const [prepared, setPrepared] = useState(false)
  const [videoReady, setVideoReady] = useState(false)
  const [busy, setBusy] = useState(false)
  const [instruction, setInstruction] = useState("")
  const [phase, setPhase] = useState<CalibrationCapturePhase | null>(null)
  const [side, setSide] = useState<"izquierda" | "derecha" | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<CalibrationState | null>(null)

  const release = useCallback(() => {
    controller.current?.abort()
    controller.current = null
    stream.current?.getTracks().forEach(track => track.stop())
    stream.current = null
    if (microphone.current) void microphone.current.close().catch(() => undefined)
    microphone.current = null
    if (video.current) video.current.srcObject = null
  }, [])

  useEffect(() => {
    alive.current = true
    return () => { alive.current = false; generation.current++; release() }
  }, [evaluationId, release])

  async function prepare() {
    const current = ++generation.current
    setBusy(true); setError(null); setResult(null); setVideoReady(false)
    setInstruction(""); setPhase(null); setSide(null)
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
      const devices = await navigator.mediaDevices.enumerateDevices()
      cameraLabel.current = devices.find(device => device.deviceId === camera.getSettings().deviceId)?.label || camera.label
      microphone.current = await createMicrophoneMonitor(media)
      if (!alive.current || current !== generation.current) { release(); return }
      if (video.current) video.current.srcObject = media
      setPrepared(true)
    } catch {
      release()
      if (alive.current && current === generation.current) {
        setPrepared(false)
        setError("No se pudo acceder a la cámara o al micrófono. Revisá los permisos y usá una conexión segura o localhost.")
      }
    } finally {
      if (alive.current && current === generation.current) setBusy(false)
    }
  }

  async function verify() {
    if (!video.current || !microphone.current || busy) return
    const current = ++generation.current
    controller.current = new AbortController()
    const signal = controller.current.signal
    setBusy(true); setError(null); setResult(null)
    setInstruction("Preparando el movimiento…"); setPhase(null); setSide(null)
    try {
      const challenge = await requestCalibrationChallenge(evaluationId)
      if (!alive.current || current !== generation.current || signal.aborted) return
      // Server directions refer to raw camera coordinates. The mirrored preview
      // uses the member's own left/right; evidence sent to the server stays raw.
      const requestedSide = challenge.action === "TURN_LEFT" ? "derecha" : "izquierda"
      setSide(requestedSide)
      const evidence = await captureCalibrationEvidence(video.current, microphone.current, signal, nextPhase => {
        if (!alive.current || current !== generation.current || signal.aborted) return
        setPhase(nextPhase)
        setInstruction(nextPhase === "CENTER" ? "Mirá al centro y quedate quieto."
          : nextPhase === "TURN" ? `Girá hacia tu ${requestedSide}.`
          : nextPhase === "RETURN" ? "Volvé al centro y quedate quieto."
          : nextPhase === "AMBIENT" ? "Guardá silencio durante 3 segundos."
          : nextPhase === "SPEAK" ? "Decí: «Estoy listo para comenzar»." : "Ahora guardá silencio y mantené la boca quieta.")
      })
      signal.throwIfAborted()
      setPhase(null)
      setInstruction("Procesando la captura… Ya podés quedarte quieto.")
      const state = await verifyEvaluationCalibration(evaluationId, {
        ...evidence, challenge_id: challenge.id, camera_label: cameraLabel.current,
      })
      if (!alive.current || current !== generation.current) return
      if (state.ready && !["single_speaker", "no_overlap", "mouth_audio_sync", "speech_pause"].every(key => state.checks[key] === true)) {
        throw new Error("El servidor no completó los nuevos controles de voz y boca. Reiniciá el backend y repetí la comprobación.")
      }
      setResult(state)
      setInstruction(""); setPhase(null)
      if (state.ready) { release(); setPrepared(false); setVideoReady(false) }
    } catch (cause) {
      if (alive.current && current === generation.current && !signal.aborted) {
        setError(cause instanceof Error ? cause.message : "No se pudo completar la calibración.")
        setInstruction(""); setPhase(null)
      }
    } finally {
      if (alive.current && current === generation.current) setBusy(false)
    }
  }

  function closeDevices() {
    generation.current++
    release(); setPrepared(false); setVideoReady(false); setBusy(false); setInstruction("")
    setPhase(null); setSide(null)
  }

  return <section aria-label="Comprobación del ambiente" className="space-y-4">
    <Card className="rounded-xl border bg-muted/20 py-0 shadow-none ring-0">
      <CardContent className="gap-4 p-4 sm:p-5">
        <h2 className="text-xs leading-relaxed font-bold text-primary uppercase">Paso 3 de 3: calibración de cámara y micrófono</h2>
        {!result?.ready && <>
          <div role="status" aria-live="assertive" aria-atomic="true" className="flex items-center gap-4 rounded-xl border-2 border-primary/30 bg-primary/10 p-4">
            {phase === "AMBIENT" || phase === "SPEAK" || phase === "PAUSE" ? <Mic className="size-9 shrink-0 text-primary" aria-hidden="true" /> : phase === "TURN" && side ? (side === "derecha"
              ? <ArrowRight className="size-12 shrink-0 text-primary" aria-hidden="true" />
              : <ArrowLeft className="size-12 shrink-0 text-primary" aria-hidden="true" />)
              : <Camera className="size-9 shrink-0 text-primary" aria-hidden="true" />}
            <div className="min-w-0 space-y-1">
              <p className="text-xs font-semibold text-primary">{phase === "AMBIENT" || phase === "SPEAK" || phase === "PAUSE" ? "Etapa 2 de 2 · Micrófono y boca" : phase ? `Paso ${phase === "CENTER" ? 1 : phase === "TURN" ? 2 : 3} de 3 · Movimiento` : busy ? "Comprobación en curso" : "Movimiento (11 s) → Fondo (3 s) → Voz y pausa (8 s)"}</p>
              <h3 className="text-lg leading-snug font-bold sm:text-xl">{instruction || "Seguí la guía, no te adelantes."}</h3>
              <p className="text-xs leading-relaxed text-muted-foreground">{phase === "AMBIENT" ? "No hables: estamos capturando el fondo. Pausá llamadas, videos y conversaciones."
                : phase === "SPEAK" ? "Tenés 4 segundos para decir la frase mirando a cámara. Después esperá el aviso de silencio."
                : phase === "PAUSE" ? "Durante estos 4 segundos no hables ni muevas la boca. Se compara el audio con el video de esta etapa."
                : "La vista previa funciona como un espejo. Primero seguí la flecha; después el micrófono se comprobará automáticamente."}</p>
            </div>
          </div>
          {phase === "AMBIENT" || phase === "SPEAK" || phase === "PAUSE" ? <ol aria-label="Pasos del micrófono" className="grid grid-cols-3 gap-2 text-center text-xs">
            {(["AMBIENT", "SPEAK", "PAUSE"] as const).map((item, index) => <li key={item} aria-current={phase === item ? "step" : undefined}
              className={`rounded-lg border px-2 py-3 ${phase === item ? "border-primary bg-primary text-primary-foreground" : "text-muted-foreground"}`}>
              {index + 1}. {item === "AMBIENT" ? "Fondo · 3 s" : item === "SPEAK" ? "Frase · 4 s" : "Pausa · 4 s"}
            </li>)}
          </ol> : <ol aria-label="Pasos del movimiento" className="grid grid-cols-3 gap-2 text-center text-xs">
            {(["CENTER", "TURN", "RETURN"] as const).map((item, index) => <li key={item} aria-current={phase === item ? "step" : undefined}
              className={`rounded-lg border px-2 py-3 ${phase === item ? "border-primary bg-primary text-primary-foreground" : "text-muted-foreground"}`}>
              <span className="block font-bold">{index + 1}. {item === "CENTER" ? "Centro" : item === "TURN" ? "Girá" : "Volvé al centro"}</span>
              {item === "TURN" && side && <span className="mt-1 block">Hacia tu {side}</span>}
            </li>)}
          </ol>}
          {!busy && <p className="text-xs leading-relaxed text-muted-foreground">La dirección aparecerá al comenzar. Primero mirá al centro; girá solo cuando veas la flecha y regresá cuando cambie la indicación. Después guardá silencio y hablá únicamente cuando aparezca la frase. No hay botones entre etapas.</p>}
        </>}
        <div className="grid items-center gap-5 sm:grid-cols-[minmax(0,280px)_minmax(0,1fr)]">
          <div className="relative flex aspect-video min-w-0 items-center justify-center overflow-hidden rounded-lg bg-zinc-900">
            <video ref={video} autoPlay muted playsInline onLoadedData={() => setVideoReady(true)}
              className={`absolute inset-0 size-full -scale-x-100 object-contain ${prepared ? "opacity-100" : "opacity-0"}`} aria-label="Vista previa de cámara" />
            {phase === "TURN" && side && <div className="absolute top-2 right-2 rounded-lg bg-primary p-1 text-primary-foreground" aria-hidden="true">
              {side === "derecha" ? <ArrowRight className="size-8" /> : <ArrowLeft className="size-8" />}
            </div>}
            <div className="pointer-events-none relative mb-5 h-24 w-[72px] rounded-[48%] border-2 border-primary" aria-hidden="true">
              {!prepared && <Camera className="absolute inset-0 m-auto size-5 text-primary" />}
            </div>
            <p className="absolute inset-x-2 bottom-3 text-center text-[11px] font-medium text-emerald-400">{result?.ready ? "Captura finalizada · cámara apagada" : prepared ? "Mantené tu rostro dentro de la guía" : "Cámara apagada · esperá para dar permiso"}</p>
          </div>
          <div className="min-w-0 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs"><span className="flex items-center gap-2 font-semibold"><Mic className="size-4 text-primary" aria-hidden="true" />Micrófono ambiental</span>
              <span className="text-muted-foreground">{result?.checks.microphone ? "Voz comprobada" : phase === "AMBIENT" ? "Capturando fondo" : phase === "SPEAK" ? "Capturando voz y video" : phase === "PAUSE" ? "Comprobando pausa" : prepared ? "Listo para comprobar" : "Sin activar"}</span>
            </div>
            <Progress value={result?.checks.microphone ? 100 : 0} aria-label="Comprobación de señal del micrófono" className="h-1.5" />
            {result?.ready ? <div className="flex items-start gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3 text-sm text-emerald-700 dark:text-emerald-400">
              <CheckCircle2 className="size-5 shrink-0" aria-hidden="true" /><div><p className="font-semibold">Comprobación superada</p><p className="mt-1 text-xs">Movimiento, ambiente sonoro, actividad de voz e identidad comprobados en esta captura.</p></div>
            </div> : <>
              <p className="text-xs leading-relaxed text-muted-foreground">{prepared ? "Cámara y micrófono preparados. Seguí las indicaciones de arriba." : "La cámara y el micrófono están apagados."}</p>
              <p className="text-xs leading-relaxed text-muted-foreground">Prepará buena iluminación, rostro centrado y una sola persona visible. Los permisos se solicitan solo cuando lo indicás.</p>
            </>}
          </div>
        </div>
        {error && <div role="alert" className="space-y-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-xs leading-relaxed text-destructive"><p>{error}</p>
          {side && error.includes("movimiento") && <p>El movimiento solicitado fue hacia tu {side}, siguiendo la flecha. Podés reintentar sin gastar tu intento; el próximo reto puede pedir el otro lado.</p>}
        </div>}
        {result?.ready ? <>
          <ul className="grid gap-2 sm:grid-cols-2">{Object.entries(result.checks).map(([key, passed]) =>
            <li key={key} className="flex items-start gap-2 text-xs leading-relaxed"><Badge variant={passed ? "secondary" : "destructive"}>{passed ? "Correcto" : "Revisar"}</Badge>{labels[key] ?? key}</li>,
          )}</ul>
          <p className="text-xs leading-relaxed text-muted-foreground">El examen no comenzó y tu intento no se descontó. El inicio de teoría y la supervisión continua se integrarán en las siguientes tareas.</p>
        </> : <>
          <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
            {!prepared && <Button className="h-auto min-h-11 whitespace-normal py-2" disabled={busy} onClick={() => void prepare()}>Preparar cámara y micrófono</Button>}
            <Button className="h-auto min-h-11 whitespace-normal py-2" disabled={!prepared || !videoReady || busy} onClick={() => void verify()}>
              {busy && prepared ? "Comprobando…" : "Comprobar ambiente e identidad"}
            </Button>
            {prepared && <Button variant="outline" className="h-auto min-h-11 whitespace-normal py-2" onClick={closeDevices}>Cerrar cámara y micrófono</Button>}
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground">La captura guiada dura unos 22 segundos: 11 de movimiento, 3 de fondo y 8 de voz con pausa. El reto vence a los 45 segundos. Se estiman varios hablantes, superposición y coincidencia entre boca y audio. No se identifica WhatsApp ni quién habla; estos controles no garantizan detectar toda llamada, pantalla o video manipulado. Podés repetir sin gastar el intento.</p>
        </>}
      </CardContent>
    </Card>
    <div className="flex flex-col-reverse justify-between gap-3 sm:flex-row">
      {onBack && <Button variant="outline" className="h-11" onClick={onBack}><ArrowLeft aria-hidden="true" />Volver a Normas</Button>}
      <Button disabled className="h-11 sm:ml-auto sm:px-6" title="El inicio del examen teórico todavía no está integrado">Comenzar primera prueba<ArrowRight aria-hidden="true" /></Button>
    </div>
  </section>
}

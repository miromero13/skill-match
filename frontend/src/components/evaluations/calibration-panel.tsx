import { useCallback, useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  requestCalibrationChallenge, verifyEvaluationCalibration, type CalibrationState,
} from "@/services/evaluation-service"
import {
  captureCalibrationEvidence, createMicrophoneMonitor, type MicrophoneMonitor,
} from "@/services/calibration-capture"

const labels: Record<string, string> = {
  lighting: "Iluminación", framing: "Encuadre", single_face: "Una sola persona visible",
  microphone: "Señal del micrófono", identity: "Coincidencia con el rostro enrolado",
  liveness: "Movimiento solicitado", passive_screen_check: "Sin patrones de pantalla evidentes (heurística)",
}

export function CalibrationPanel({ evaluationId }: { evaluationId: string }) {
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
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("Camera access unavailable")
      const media = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640, max: 1280 }, height: { ideal: 480, max: 960 }, facingMode: "user" },
        audio: true,
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
    try {
      const challenge = await requestCalibrationChallenge(evaluationId)
      if (!alive.current || current !== generation.current) return
      const side = challenge.action === "TURN_LEFT" ? "izquierda" : "derecha"
      setInstruction(`Mirá al centro, girá hacia la ${side} de la imagen y volvé al centro. Decí «listo» durante la captura.`)
      const evidence = await captureCalibrationEvidence(video.current, microphone.current, signal)
      signal.throwIfAborted()
      const state = await verifyEvaluationCalibration(evaluationId, {
        ...evidence, challenge_id: challenge.id, camera_label: cameraLabel.current,
      })
      if (!alive.current || current !== generation.current) return
      setResult(state)
      setInstruction("")
      if (state.ready) { release(); setPrepared(false); setVideoReady(false) }
    } catch (cause) {
      if (alive.current && current === generation.current && !signal.aborted) {
        setError(cause instanceof Error ? cause.message : "No se pudo completar la calibración.")
        setInstruction("")
      }
    } finally {
      if (alive.current && current === generation.current) setBusy(false)
    }
  }

  function closeDevices() {
    generation.current++
    release(); setPrepared(false); setVideoReady(false); setBusy(false); setInstruction("")
  }

  return <section aria-label="Comprobación del ambiente" className="space-y-4 rounded-lg border p-4">
    <h2 className="font-semibold">Comprobación del ambiente e identidad</h2>
    <p className="text-sm">Prepará buena iluminación, rostro centrado y una sola persona visible. La cámara y el micrófono se activan únicamente cuando lo solicitás.</p>
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    {result?.ready ? <>
      <p className="font-medium">Comprobación superada</p>
      <ul className="space-y-2">{Object.entries(result.checks).map(([key, passed]) =>
        <li key={key} className="flex flex-wrap items-center gap-2"><Badge variant={passed ? "secondary" : "destructive"}>{passed ? "Correcto" : "Revisar"}</Badge>{labels[key] ?? key}</li>,
      )}</ul>
      <p>El examen no comenzó y tu intento no se descontó. El inicio de teoría y la supervisión continua se integrarán en las siguientes tareas.</p>
    </> : <>
      <video ref={video} autoPlay muted playsInline onLoadedData={() => setVideoReady(true)}
        className="aspect-video w-full rounded-lg bg-muted object-contain" aria-label="Vista previa de cámara" />
      <p role="status" aria-live="assertive">{instruction || (prepared ? "Mirá al centro y preparate para girar hacia el lado indicado y regresar al centro." : "La cámara y el micrófono están apagados.")}</p>
      <div className="flex flex-wrap gap-2">
        {!prepared && <Button disabled={busy} onClick={() => void prepare()}>Preparar cámara y micrófono</Button>}
        <Button disabled={!prepared || !videoReady || busy} onClick={() => void verify()}>
          {busy && prepared ? "Comprobando…" : "Comprobar ambiente e identidad"}
        </Button>
        {prepared && <Button variant="outline" onClick={closeDevices}>Cerrar cámara y micrófono</Button>}
      </div>
      <p className="text-xs text-muted-foreground">La captura del reto dura unos tres segundos y vence a los cinco. Si falla, podés corregir el ambiente y repetir sin gastar el intento. Las comprobaciones visuales no garantizan detectar toda pantalla o video manipulado.</p>
    </>}
  </section>
}

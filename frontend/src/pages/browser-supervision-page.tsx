import { useEffect, useRef, useState } from "react"
import { Link } from "react-router-dom"
import {
  AlertCircle,
  Camera,
  CheckCircle2,
  Maximize2,
  Mic,
  Shield,
  User,
  Volume2,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { useAuthStore } from "@/stores/auth-store"
import {
  BrowserMonitor,
  IncidentQueue,
  readBrowserLedger,
  readBrowserTrial,
  sendAVWindow,
  sendBrowserIncidents,
  startBrowserTrial,
  trialAction,
  type IncidentKind,
  type LedgerIncident,
  type Trial,
} from "@/services/browser-supervision"

interface Runtime {
  id: string
  queue: IncidentQueue
  monitor: BrowserMonitor
  timer: ReturnType<typeof setInterval> | null
  closing: boolean
  release: () => void
}

const labels: Record<string, string> = {
  AWAY: "Salida / pérdida de foco",
  RETURN: "Regreso",
  COPY: "Copiar",
  CUT: "Cortar",
  PASTE: "Pegar",
  DROP: "Arrastrar / soltar",
  CONTEXT_MENU: "Menú contextual",
  FULLSCREEN_EXIT: "Salida de pantalla completa",
  OFFLINE: "Sin conexión",
  ONLINE: "Conexión recuperada",
  PAGE_EXIT: "Salida de página",
  SESSION_OPEN: "Inicio de prueba",
  SESSION_RESUME: "Reanudación",
  FACE_ABSENT: "Rostro ausente en cámara",
  MULTIPLE_FACES: "Múltiples rostros detectados",
  IDENTITY_MISMATCH: "Rostro no coincide con el perfil",
  HEAD_POSE_DOWN: "Cabeza orientada hacia abajo sostenida",
  HEAD_POSE_SIDE: "Cabeza girada a los costados sostenida",
  VOICE_DETECTED: "Voz / susurro detectado",
  MULTIPLE_SPEAKERS: "Voces simultáneas / más de un hablante",
  HIGH_NOISE: "Ruido ambiental excesivo",
  DEVICE_DISCONNECTED: "Desconexión de cámara o micrófono",
  STREAM_ERROR: "Fallo técnico en la captura audiovisual",
}

const message = (error: unknown) =>
  error instanceof Error ? error.message : "No se pudo completar la operación."

export function BrowserSupervisionPage() {
  const owner = useAuthStore((state) => state.user?.id)
  const area = useRef<HTMLDivElement>(null)
  const runtime = useRef<Runtime | null>(null)
  const generation = useRef(0)
  const tab = useRef(crypto.randomUUID())

  // Video / Audio refs
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const avTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const vuAnimationRef = useRef<number | null>(null)
  const modeRef = useRef<"QUIET" | "SPEAKING">("QUIET")

  const [trial, setTrial] = useState<Trial | null>(null)
  const [accepted, setAccepted] = useState(false)
  const [active, setActive] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")
  const [pending, setPending] = useState(0)
  const [rows, setRows] = useState<LedgerIncident[]>([])
  const [total, setTotal] = useState(0)

  // AV State
  const [avActive, setAvActive] = useState(false)
  const [mode, setMode] = useState<"QUIET" | "SPEAKING">("QUIET")
  const [faceCount, setFaceCount] = useState<number>(1)
  const [headOrientation, setHeadOrientation] = useState<string>("CENTER")
  const [identityMatch, setIdentityMatch] = useState<boolean | null>(null)
  const [speechDetected, setSpeechDetected] = useState(false)
  const [noiseLevel, setNoiseLevel] = useState(0)
  const [vuLevel, setVuLevel] = useState(0)
  const [deviceError, setDeviceError] = useState("")

  const lastKey = `sm43:last:${owner}`

  useEffect(() => {
    modeRef.current = mode
  }, [mode])

  function stopAV() {
    if (vuAnimationRef.current) {
      cancelAnimationFrame(vuAnimationRef.current)
      vuAnimationRef.current = null
    }
    if (avTimerRef.current) {
      clearInterval(avTimerRef.current)
      avTimerRef.current = null
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }
    if (audioContextRef.current && audioContextRef.current.state !== "closed") {
      void audioContextRef.current.close().catch(() => undefined)
      audioContextRef.current = null
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null
    }
    setAvActive(false)
    setVuLevel(0)
  }

  function stop() {
    stopAV()
    const current = runtime.current
    runtime.current = null
    if (current) {
      current.monitor.stop()
      if (current.timer) clearInterval(current.timer)
      current.release()
    }
  }

  async function ledger(id: string, more = false) {
    const version = generation.current
    const response = await readBrowserLedger(id, more ? rows.at(-1)?.sequence ?? 0 : 0)
    if (version !== generation.current) return
    setRows((previous) => (more ? [...previous, ...response.data] : response.data))
    setTotal(response.count ?? 0)
  }

  useEffect(() => {
    const version = ++generation.current
    setTrial(null)
    setRows([])
    setTotal(0)
    setActive(false)
    try {
      const id = localStorage.getItem(`sm43:last:${owner}`)
      if (id && /^[0-9a-f-]{36}$/i.test(id))
        void readBrowserTrial(id)
          .then(async (saved) => {
            if (version !== generation.current) return
            setTrial(saved)
            await ledger(saved.id)
          })
          .catch((cause) => {
            if (version === generation.current) setError(message(cause))
          })
    } catch {
      setError("El almacenamiento local no está disponible; no se puede garantizar recuperación.")
    }
    return () => {
      generation.current++
      stop()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [owner])

  async function startAV(
    trialId: string,
    tabId: string,
    emit: (event: { kind: IncidentKind; duration_ms?: number }) => void,
  ) {
    if (!navigator.mediaDevices?.getUserMedia) {
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 480 }, height: { ideal: 360 } },
        audio: { channelCount: 1, echoCancellation: true },
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        void videoRef.current.play().catch(() => undefined)
      }

      stream.getTracks().forEach((track) => {
        track.addEventListener("ended", () => {
          emit({ kind: "DEVICE_DISCONNECTED" })
          setDeviceError(`Dispositivo de ${track.kind === "video" ? "cámara" : "micrófono"} desconectado.`)
        })
        track.addEventListener("mute", () => {
          emit({ kind: "DEVICE_DISCONNECTED" })
          setDeviceError(`Pérdida temporal de señal en ${track.kind === "video" ? "cámara" : "micrófono"}.`)
        })
      })

      try {
        const AudioCtx =
          window.AudioContext ||
          (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
        if (AudioCtx) {
          const audioCtx = new AudioCtx()
          audioContextRef.current = audioCtx
          const source = audioCtx.createMediaStreamSource(stream)
          const analyser = audioCtx.createAnalyser()
          analyser.fftSize = 256
          source.connect(analyser)
          analyserRef.current = analyser

          const dataArray = new Uint8Array(analyser.frequencyBinCount)
          const updateVU = () => {
            if (!streamRef.current) return
            analyser.getByteFrequencyData(dataArray)
            let sum = 0
            for (let i = 0; i < dataArray.length; i++) {
              sum += dataArray[i]
            }
            const avg = sum / dataArray.length
            setVuLevel(Math.min(100, Math.round((avg / 128) * 100)))
            vuAnimationRef.current = requestAnimationFrame(updateVU)
          }
          vuAnimationRef.current = requestAnimationFrame(updateVU)
        }
      } catch {
        // Audio context optional
      }

      setAvActive(true)
      setDeviceError("")

      let collectedFrames: string[] = []
      let sampleCounter = 0

      const sampleInterval = setInterval(() => {
        if (!streamRef.current || !videoRef.current || !canvasRef.current) return
        sampleCounter++
        try {
          const canvas = canvasRef.current
          const video = videoRef.current
          if (video.videoWidth > 0 && video.videoHeight > 0) {
            canvas.width = 320
            canvas.height = 240
            const ctx = canvas.getContext("2d")
            if (ctx) {
              ctx.drawImage(video, 0, 0, 320, 240)
              collectedFrames.push(canvas.toDataURL("image/jpeg", 0.6))
            }
          }
        } catch {
          // ignore frame capture error
        }

        if (sampleCounter >= 4) {
          sampleCounter = 0
          const framesToSend = [...collectedFrames]
          collectedFrames = []

          if (framesToSend.length > 0) {
            void sendAVWindow(trialId, {
              tab_id: tabId,
              window_id: crypto.randomUUID(),
              observed_at: new Date().toISOString(),
              duration_ms: 8000,
              mode: modeRef.current,
              frames: framesToSend,
            })
              .then((res) => {
                setFaceCount(res.face_count)
                setHeadOrientation(res.head_orientation)
                setIdentityMatch(res.identity_match)
                setSpeechDetected(res.speech_detected)
                setNoiseLevel(res.noise_level)
                if (res.anomalies.length > 0) {
                  void ledger(trialId)
                }
              })
              .catch(() => undefined)
          }
        }
      }, 2000)

      avTimerRef.current = sampleInterval
    } catch {
      emit({ kind: "STREAM_ERROR" })
      setDeviceError("No se pudo iniciar la cámara o micrófono. Verificá los permisos del navegador.")
    }
  }

  async function start() {
    if (!owner || !area.current) return
    stop()
    setActive(false)
    setBusy(true)
    setError("")
    const version = ++generation.current
    const tabId = crypto.randomUUID()
    tab.current = tabId
    let claimed: string | null = null
    const requestedAt = performance.now()
    try {
      const result = await startBrowserTrial(tabId)
      claimed = result.trial.id
      if (version !== generation.current) {
        void trialAction(claimed, tabId, "release", true).catch(() => undefined)
        return
      }
      if (performance.now() - requestedAt >= 15000)
        throw new Error("La activación llegó tarde. Reactivá la prueba para confirmar autorización.")
      const resumed = localStorage.getItem(lastKey) === claimed
      localStorage.setItem(lastKey, claimed)
      setTrial(result.trial)
      setNotice(result.message)
      const pause = (text: string) => {
        if (version === generation.current) {
          setError(text)
          setActive(false)
        }
      }
      let fatal = false
      let deadline = requestedAt + 15000
      let current: Runtime
      const queue = new IncidentQueue(
        `sm43:queue:${owner}:${claimed}`,
        async (events) => {
          const response = await sendBrowserIncidents(result.trial.id, tabId, events)
          if (runtime.current !== current || performance.now() >= deadline)
            throw new Error("Confirmación tardía: los incidentes se conservan para reintentar.")
          return response
        },
        (text) => {
          fatal = true
          pause(text)
        },
      )
      const emit = (event: Parameters<IncidentQueue["add"]>[0]) => {
        if (runtime.current !== current || current.closing) return
        queue.add(event)
        setPending(queue.size)
        void queue
          .flush()
          .then(() => {
            if (runtime.current === current) setPending(queue.size)
          })
          .catch((cause) => pause(message(cause)))
      }
      const monitor = new BrowserMonitor(area.current, emit, setNotice)
      current = {
        id: claimed,
        queue,
        monitor,
        timer: null,
        closing: false,
        release: () => {
          void trialAction(result.trial.id, tabId, "release", true).catch(() => undefined)
        },
      }
      runtime.current = current
      let nextRenew = performance.now() + 5000
      let renewing = false
      const renew = async () => {
        if (renewing || runtime.current !== current || current.closing) return
        renewing = true
        const sentAt = performance.now()
        try {
          await trialAction(current.id, tabId, "heartbeat")
          if (runtime.current !== current || current.closing) return
          deadline = sentAt + 15000
          if (performance.now() >= deadline) throw new Error("La renovación llegó tarde. Reactivá la prueba.")
          await queue.flush()
          if (runtime.current === current && !current.closing) {
            setPending(queue.size)
            monitor.start()
            setActive(!fatal)
          }
        } catch (cause) {
          if (runtime.current === current && !current.closing) {
            monitor.stop()
            pause(message(cause))
          }
        } finally {
          renewing = false
        }
      }
      current.timer = setInterval(() => {
        if (performance.now() >= deadline) {
          monitor.stop()
          setActive(false)
          setError("Autorización de pestaña sin confirmar. Reactivá la prueba para continuar.")
        }
        if (performance.now() >= nextRenew) {
          nextRenew = performance.now() + 5000
          void renew()
        }
      }, 1000)
      monitor.start()
      queue.add({ kind: resumed ? "SESSION_RESUME" : "SESSION_OPEN" })
      setPending(queue.size)
      await queue.flush()
      if (runtime.current === current) {
        setPending(queue.size)
        setActive(!fatal)
        await ledger(current.id)
        void startAV(claimed, tabId, emit)
      }
    } catch (cause) {
      if (version === generation.current) {
        setError(message(cause))
        setActive(false)
        if (!runtime.current && claimed) void trialAction(claimed, tabId, "release", true).catch(() => undefined)
      }
    } finally {
      if (version === generation.current) setBusy(false)
    }
  }

  async function close() {
    stopAV()
    const current = runtime.current
    if (!current) return
    setBusy(true)
    setActive(false)
    setError("")
    current.closing = true
    current.monitor.stop()
    if (current.timer) clearInterval(current.timer)
    try {
      await current.queue.flush()
      const result = await trialAction(current.id, tab.current, "close")
      if (runtime.current !== current) return
      current.monitor.stop()
      if (current.timer) clearInterval(current.timer)
      runtime.current = null
      setTrial(result.trial)
      setPending(0)
      setNotice(result.message)
      await ledger(current.id)
    } catch (cause) {
      setError(message(cause))
    } finally {
      setBusy(false)
    }
  }

  async function fullscreen() {
    try {
      if (!area.current?.requestFullscreen)
        throw new Error("Este navegador no permite pantalla completa. La prueba puede continuar sin ese modo.")
      await area.current.requestFullscreen()
    } catch (cause) {
      setError(message(cause))
    }
  }

  return (
    <section className="mx-auto w-full max-w-4xl space-y-5 p-4 sm:p-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Prueba de supervisión continua</h1>
        <p className="text-sm text-muted-foreground">
          SM-43 & SM-49 · Navegador, cámara y micrófono en tiempo real. No inicia un examen, no consume intentos ni aplica sanciones automáticas.
        </p>
      </div>

      <Card>
        <CardContent className="space-y-4 p-5">
          <h2 className="font-semibold">Normas y controles activos</h2>
          <p className="text-sm text-muted-foreground">
            Se supervisa en tiempo real la presencia facial, orientación sostenida de la cabeza, nivel de audio/voz,
            pérdida de foco, cambio de pestaña, conectividad y portapapeles dentro del área de prueba.
          </p>

          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 rounded-lg border bg-muted/30 p-3">
            <div className="space-y-0.5">
              <Label className="text-sm font-medium">Modo de evaluación audiovisual</Label>
              <p className="text-xs text-muted-foreground">
                {mode === "QUIET"
                  ? "Modo Silencio: Alerta ante voces o susurros detectados (examen escrito / código)."
                  : "Modo Habla: Permite una voz activa para preguntas orales o defensas técnicas."}
              </p>
            </div>
            <Select
              value={mode}
              disabled={active}
              onValueChange={(val: "QUIET" | "SPEAKING") => setMode(val)}
            >
              <SelectTrigger className="w-44">
                <SelectValue placeholder="Seleccionar modo" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="QUIET">Modo Silencio</SelectItem>
                <SelectItem value="SPEAKING">Modo Habla</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-start gap-3">
            <Checkbox
              id="browser-trial-consent"
              checked={accepted}
              disabled={busy || active}
              onCheckedChange={(value) => setAccepted(value === true)}
            />
            <Label htmlFor="browser-trial-consent" className="cursor-pointer text-sm">
              Acepto los controles de supervisión de navegador, cámara y micrófono para esta sesión de prueba.
            </Label>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button onClick={() => void start()} disabled={!accepted || busy || active}>
              {busy ? "Procesando…" : "Activar prueba"}
            </Button>
            <Button variant="outline" onClick={() => void close()} disabled={!runtime.current || busy}>
              Cerrar prueba
            </Button>
            <Button variant="outline" onClick={() => void fullscreen()} disabled={!active}>
              <Maximize2 className="mr-1.5 size-4" />
              Pantalla completa opcional
            </Button>
          </div>

          {error && (
            <p role="alert" className="text-sm text-destructive font-medium">
              {error}
            </p>
          )}
          {deviceError && (
            <p className="text-sm text-amber-600 dark:text-amber-400 flex items-center gap-1.5 font-medium">
              <AlertCircle className="size-4 shrink-0" />
              {deviceError}
            </p>
          )}
          {notice && (
            <p role="status" className="text-sm text-muted-foreground">
              {notice}
            </p>
          )}
          <p className="text-xs text-muted-foreground">
            Estado: {active ? "supervisión activa" : "área deshabilitada"} · Pendientes de confirmación: {pending}
          </p>
        </CardContent>
      </Card>

      {/* Visual & Audio Supervision Panel */}
      <Card>
        <CardContent className="space-y-4 p-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Camera className="size-5 text-emerald-600 dark:text-emerald-400" />
              <h2 className="font-semibold">Supervisión audiovisual continua en vivo</h2>
            </div>
            <Badge variant={avActive ? "default" : "outline"} className={avActive ? "bg-emerald-600" : ""}>
              {avActive ? "Cámara y audio activos" : "Dispositivos en espera"}
            </Badge>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-12 gap-5 items-start">
            {/* Camera Preview Box */}
            <div className="md:col-span-5 flex flex-col items-center">
              <div className="relative w-full aspect-[4/3] rounded-xl overflow-hidden border bg-neutral-950 flex items-center justify-center">
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  className={`w-full h-full object-cover ${avActive ? "block" : "hidden"}`}
                />
                {!avActive && (
                  <div className="text-center p-4 space-y-2 text-muted-foreground">
                    <Camera className="size-10 mx-auto opacity-40" />
                    <p className="text-xs">
                      La cámara se activa al pulsar &laquo;Activar prueba&raquo; y se libera completamente al cerrar o navegar.
                    </p>
                  </div>
                )}
                {/* Guide overlay */}
                {avActive && (
                  <div className="absolute inset-0 pointer-events-none border-2 border-emerald-500/30 rounded-xl" />
                )}
              </div>
              <canvas ref={canvasRef} className="hidden" />

              {/* VU Meter */}
              <div className="w-full mt-3 space-y-1">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Mic className="size-3.5" /> Nivel de micrófono
                  </span>
                  <span>{vuLevel}%</span>
                </div>
                <div className="w-full h-2 rounded-full bg-muted overflow-hidden">
                  <div
                    className={`h-full transition-all duration-75 ${
                      vuLevel > 75
                        ? "bg-rose-500"
                        : vuLevel > 40
                        ? "bg-amber-500"
                        : "bg-emerald-500"
                    }`}
                    style={{ width: `${vuLevel}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Live Telemetry Status Badges */}
            <div className="md:col-span-7 space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {/* Face presence */}
                <div className="rounded-lg border p-3 bg-card space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground flex items-center gap-1.5">
                      <User className="size-3.5" /> Presencia facial
                    </span>
                    <Badge
                      variant={faceCount === 1 ? "secondary" : "destructive"}
                      className="text-[11px]"
                    >
                      {faceCount === 0
                        ? "Ausente"
                        : faceCount === 1
                        ? "1 en encuadre"
                        : `${faceCount} personas`}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {faceCount === 1
                      ? "Rostro único validado con YuNet."
                      : faceCount === 0
                      ? "Alerta: No se detecta persona frente a la cámara."
                      : "Alerta: Múltiples personas en pantalla."}
                  </p>
                </div>

                {/* Head orientation */}
                <div className="rounded-lg border p-3 bg-card space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground flex items-center gap-1.5">
                      <Shield className="size-3.5" /> Orientación de cabeza
                    </span>
                    <Badge
                      variant={headOrientation === "CENTER" ? "secondary" : "destructive"}
                      className="text-[11px]"
                    >
                      {headOrientation === "CENTER"
                        ? "Al centro"
                        : headOrientation === "DOWN"
                        ? "Hacia abajo"
                        : "Lateral"}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {headOrientation === "CENTER"
                      ? "Postura centrada normal."
                      : headOrientation === "DOWN"
                      ? "Mirada prolongada hacia abajo."
                      : "Giro lateral pronunciado."}
                  </p>
                </div>

                {/* Identity match */}
                <div className="rounded-lg border p-3 bg-card space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground flex items-center gap-1.5">
                      <CheckCircle2 className="size-3.5" /> Cotejo con perfil
                    </span>
                    <Badge
                      variant={
                        identityMatch === true
                          ? "secondary"
                          : identityMatch === false
                          ? "destructive"
                          : "outline"
                      }
                      className="text-[11px]"
                    >
                      {identityMatch === true
                        ? "Coincide"
                        : identityMatch === false
                        ? "Discrepancia"
                        : "Pendiente"}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {identityMatch === true
                      ? "Embedding SFace coincide con registro oficial."
                      : identityMatch === false
                      ? "Alerta: Posible suplantación a mitad de prueba."
                      : "Comparación periódica en curso."}
                  </p>
                </div>

                {/* Audio activity */}
                <div className="rounded-lg border p-3 bg-card space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground flex items-center gap-1.5">
                      <Volume2 className="size-3.5" /> Actividad acústica
                    </span>
                    <Badge
                      variant={
                        mode === "QUIET" && speechDetected
                          ? "destructive"
                          : noiseLevel > 0.15
                          ? "destructive"
                          : "secondary"
                      }
                      className="text-[11px]"
                    >
                      {speechDetected
                        ? "Voz detectada"
                        : noiseLevel > 0.15
                        ? "Ruido alto"
                        : "Silencio"}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {speechDetected
                      ? mode === "QUIET"
                        ? "Alerta: Voz accesoria en silencio."
                        : "Voz registrada dentro de lo esperado."
                      : "Sin actividad vocal anómala."}
                  </p>
                </div>
              </div>

              <p className="text-[11px] text-muted-foreground italic border-t pt-2">
                * Estimación de orientación basada en landmarks faciales locales (PnP). No realiza seguimiento ocular de precisión ni detección de smartphones.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Supervised Text Area */}
      <div ref={area} className="space-y-3 rounded-xl border bg-card p-5">
        <Label htmlFor="supervised-area">Área supervisada</Label>
        <Textarea
          id="supervised-area"
          aria-label="Área supervisada"
          disabled={!active}
          placeholder="Escribí una frase, seleccioná texto e intentá copiar, cortar, pegar o arrastrar contenido aquí."
          className="min-h-36"
        />
        <p className="text-xs text-muted-foreground">
          El texto es local y no se envía al backend. Fuera de esta área el portapapeles funciona normalmente.
        </p>
      </div>

      {/* Persistent Incident Ledger */}
      <Card>
        <CardContent className="space-y-3 p-5">
          <h2 className="font-semibold">Bitácora de prueba · {total} incidentes confirmados</h2>
          {trial && (
            <p className="break-all text-xs text-muted-foreground">
              Sesión: {trial.id} · {trial.closed_at ? "cerrada" : "abierta"}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              disabled={!trial}
              onClick={() => {
                if (trial) void ledger(trial.id).catch((cause) => setError(message(cause)))
              }}
            >
              Actualizar bitácora
            </Button>
            {rows.length < total && (
              <Button
                variant="outline"
                onClick={() => {
                  if (trial) void ledger(trial.id, true).catch((cause) => setError(message(cause)))
                }}
              >
                Cargar más incidentes
              </Button>
            )}
          </div>
          <ol className="max-h-96 space-y-2 overflow-y-auto text-sm" aria-label="Incidentes confirmados">
            {rows.map((row) => (
              <li key={row.event_id} className="rounded-lg border p-3">
                <strong>
                  {row.sequence}. {labels[row.kind] ?? row.kind}
                </strong>{" "}
                · {row.duration_ms} ms
                <p className="text-xs text-muted-foreground">
                  Reportado: {new Date(row.observed_at).toLocaleString()} · Recibido:{" "}
                  {new Date(row.received_at).toLocaleString()}
                </p>
              </li>
            ))}
          </ol>
          {!rows.length && (
            <p className="text-sm text-muted-foreground">Sin incidentes confirmados para mostrar.</p>
          )}
        </CardContent>
      </Card>

      <Button variant="outline" asChild>
        <Link to="/app/teaching-skills">Salir de la prueba</Link>
      </Button>
    </section>
  )
}

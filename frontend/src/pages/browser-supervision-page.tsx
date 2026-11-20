import { useEffect, useRef, useState } from "react"
import { Link, useLocation } from "react-router-dom"
import {
  AlertCircle,
  Camera,
  CheckCircle2,
  Eye,
  Maximize2,
  Mic,
  Shield,
  User,
  Volume2,
} from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { CalibrationGate, isCalibrated } from "@/components/integrity/calibration-gate"
import { TrialLabelSelect, type TrialLabel } from "@/components/integrity/trial-label-select"
import { useAvSupervision } from "@/hooks/use-av-supervision"
import { useTrialSession } from "@/hooks/use-trial-session"
import { useAuthStore } from "@/stores/auth-store"
import { calibrateGaze, calibrateVoice, type GazeCalibrationPoint } from "@/services/browser-supervision"

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
  HEAD_POSE_UP: "Cabeza orientada hacia arriba sostenida",
  GAZE_AWAY: "Mirada fuera de la pantalla sostenida",
  GAZE_AWAY_UP: "Mirada hacia arriba sostenida",
  GAZE_AWAY_DOWN: "Mirada hacia abajo sostenida",
  GAZE_AWAY_LEFT: "Mirada a la izquierda sostenida",
  GAZE_AWAY_RIGHT: "Mirada a la derecha sostenida",
  EYES_CLOSED: "Ojos cerrados de forma sostenida",
  CLIENT_MISMATCH: "El navegador contradice la medición del servidor",
  VOICE_DETECTED: "Voz detectada sin movimiento labial coincidente",
  MULTIPLE_SPEAKERS: "Voces simultáneas / más de un hablante",
  HIGH_NOISE: "Ruido ambiental excesivo",
  DEVICE_DISCONNECTED: "Desconexión de cámara o micrófono",
  STREAM_ERROR: "Fallo técnico en la captura audiovisual",
  MODEL_UNAVAILABLE: "Modelo de IA no disponible",
  VIDEO_MISSING: "Sin video",
  AUDIO_MISSING: "Sin audio",
  WINDOW_GAP: "Supervisión interrumpida",
  FACE_OCCLUDED: "Rostro cubierto",
  MOUTH_OCCLUDED: "Boca cubierta",
  CAMERA_BLOCKED: "Cámara tapada o congelada",
  VOICE_MISMATCH: "La voz no coincide con la persona",
  VOICE_UNVERIFIED: "Voz sin verificar",
  LIP_SYNC_MISMATCH: "La voz no coincide con los labios",
  BACKGROUND_AUDIO: "Audio de fondo o reproducción",
}

const message = (error: unknown) =>
  error instanceof Error ? error.message : "No se pudo completar la operación."

export function BrowserSupervisionPage() {
  const owner = useAuthStore((state) => state.user?.id)
  // A different member starts from a clean page: the key remounts everything instead of resetting state in effects.
  return <SupervisionTrial key={owner ?? "anonymous"} owner={owner} />
}

function SupervisionTrial({ owner }: { owner: string | undefined }) {
  const location = useLocation()
  const autoStart = (location.state as { autoStart?: boolean } | null)?.autoStart === true
  const area = useRef<HTMLDivElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const overlayCanvasRef = useRef<HTMLCanvasElement>(null)
  const [accepted, setAccepted] = useState(autoStart)
  const [trialLabel, setTrialLabel] = useState<TrialLabel>("normal")

  const session = useTrialSession({
    owner,
    areaRef: area,
    onReady: (handle) => void av.start(handle),
    onSuspend: () => av.stop(),
    onResume: (handle) => void av.start(handle),
    onEnd: () => av.stop(),
  })
  const { trial, active, busy, error, notice, pending, rows, total, start: startSession } = session

  useEffect(() => {
    if (!autoStart || !owner) return
    // Defer to a macrotask so React StrictMode's simulated unmount cancels the first pass before claiming a lease.
    const timer = window.setTimeout(() => {
      void startSession()
    }, 0)
    return () => window.clearTimeout(timer)
  }, [autoStart, owner, startSession])
  const av = useAvSupervision({
    videoRef,
    canvasRef,
    overlayCanvasRef,
    windowsEnabled: active && isCalibrated(trial),
    onAnomalies: () => void session.refreshLedger().catch(() => undefined),
    label: import.meta.env.DEV ? trialLabel : undefined,
  })
  const { avActive, vuLevel, deviceError, avStatus, lookingAway, gazeNotice, gazeLive } = av
  const {
    faceCount, headOrientation, identityMatch, faceCovered, mouthCovered, cameraBlocked, speechDetected,
    mouthMoving, mouthSync, multipleSpeakers, voiceMatch, lipSync, noiseLevel,
  } = av.telemetry
  const presenceAlert = cameraBlocked || faceCovered || mouthCovered

  async function submitGazeCalibration(points: GazeCalibrationPoint[]) {
    if (!trial) throw new Error("La prueba no está activa.")
    const { result, message: serverMessage } = await calibrateGaze(trial.id, session.tabId(), points)
    av.setZone(result.zone)
    session.setTrial((previous) => (previous ? { ...previous, gaze_zone: result.zone } : previous))
    return { message: serverMessage }
  }

  async function submitVoiceCalibration(request: Parameters<typeof calibrateVoice>[2]) {
    if (!trial) throw new Error("La prueba no está activa.")
    const { result, message: serverMessage } = await calibrateVoice(trial.id, session.tabId(), request)
    session.setTrial((previous) => (previous ? { ...previous, voice_enrolled: result.voice_enrolled } : previous))
    return { message: serverMessage }
  }

  /** What the acoustic card says: ownership of the voice first, then its link with the lips. */
  function acousticStatus(): { label: string; text: string; alert: boolean } {
    if (multipleSpeakers)
      return {
        label: "Voces / audio de fondo",
        text: "Alerta: Se detectaron múltiples voces o sonido multimedia de fondo (TV/serie/terceros).",
        alert: true,
      }
    if (speechDetected && voiceMatch === false)
      return {
        label: "Voz distinta a la calibrada",
        text: "Alerta: la voz no coincide con la huella de voz calibrada.",
        alert: true,
      }
    if (speechDetected && lipSync === "unsynced")
      return {
        label: "Voz sin labios coincidentes",
        text: "Alerta: la voz no coincide con el movimiento de tus labios.",
        alert: true,
      }
    if (speechDetected && mouthSync === false)
      return { label: "Voz sin boca coincidente", text: "Alerta: Se detectó voz sin movimiento labial coincidente.", alert: true }
    if (speechDetected && !trial?.voice_enrolled)
      return {
        label: "Voz sin verificar",
        text: "Calibrá tu voz para poder comprobar que quien habla sos vos.",
        alert: false,
      }
    if (speechDetected)
      return {
        label: mouthSync ? "Voz propia (boca activa)" : "Voz detectada",
        text: mouthSync
          ? "Habla propia verificada: única voz y coincidente con tu movimiento labial."
          : "Voz detectada: todavía no hay evidencia suficiente de los labios.",
        alert: false,
      }
    if (noiseLevel > 0.14) return { label: "Ruido alto", text: "Alerta: Ruido ambiental excesivo.", alert: true }
    return {
      label: mouthMoving ? "Boca en movimiento" : "Silencio",
      text: "Sin voces externas. Si hablás, se verifica tu voz y tu movimiento labial.",
      alert: false,
    }
  }

  async function fullscreen() {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen()
        return
      }
      const target = document.documentElement ?? area.current
      if (!target?.requestFullscreen)
        throw new Error("Este navegador no permite pantalla completa. La prueba puede continuar sin ese modo.")
      await target.requestFullscreen()
    } catch (cause) {
      session.setError(message(cause))
    }
  }

  const acoustic = acousticStatus()

  /** Live eye-only gaze direction from iris position inside the eye, independent of head pose. */
  function irisDirectionStatus(): { label: string; text: string; variant: "secondary" | "destructive" | "outline" } {
    if (!avActive || !gazeLive) {
      return { label: "En espera", text: "Esperando detección de iris en vivo.", variant: "outline" }
    }
    if (gazeLive.blink) {
      return { label: "Parpadeo", text: "Ojos cerrados momentáneamente.", variant: "outline" }
    }
    const { gazeH, gazeV } = gazeLive
    if (gazeH === null || gazeV === null) {
      return { label: "Sin lectura", text: "No se distinguen ambos iris.", variant: "outline" }
    }
    const T = 0.22
    const dirs: string[] = []
    if (gazeV < -T) dirs.push("Arriba")
    else if (gazeV > T) dirs.push("Abajo")
    if (gazeH > T) dirs.push("Izquierda")
    else if (gazeH < -T) dirs.push("Derecha")
    const coords = `H: ${gazeH.toFixed(2)} · V: ${gazeV.toFixed(2)}`
    if (dirs.length === 0) {
      return { label: "Al centro", text: `Mirada centrada (${coords}).`, variant: "secondary" }
    }
    return {
      label: dirs.join(" · "),
      text: `Mirando ${dirs.join(" y ").toLowerCase()} sin necesidad de mover la cabeza (${coords}).`,
      variant: "destructive",
    }
  }

  const irisStatus = irisDirectionStatus()

  return (
    <div className="min-h-screen bg-background text-foreground">
      <section className="mx-auto w-full max-w-4xl space-y-5 p-4 sm:p-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Prueba de supervisión continua</h1>
        <p className="text-sm text-muted-foreground">
          SM-43 & SM-49 · Navegador, cámara y micrófono en tiempo real. No inicia un examen, no consume intentos ni aplica sanciones automáticas.
        </p>
      </div>

      {import.meta.env.DEV && <TrialLabelSelect value={trialLabel} onChange={setTrialLabel} />}

      <Card>
        <CardContent className="space-y-4 p-5">
          <h2 className="font-semibold">Normas y controles activos</h2>
          <p className="text-sm text-muted-foreground">
            Se supervisa en tiempo real la presencia facial, orientación sostenida de la cabeza y de la mirada (no podés
            mirar abajo, arriba ni a los costados fuera de la pantalla por más de un segundo),
            sincronía entre voz y movimiento de boca (podés hablar en voz alta siempre que tu boca coincida con el audio),
            pérdida de foco, cambio de pestaña y portapapeles dentro del área de prueba.
          </p>

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
            <Button onClick={() => void session.start()} disabled={!accepted || busy || active}>
              {busy ? "Procesando…" : "Activar prueba"}
            </Button>
            <Button variant="outline" onClick={() => void session.close()} disabled={!session.open || busy}>
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
          {avStatus && (
            <Alert variant="destructive" data-testid="av-status">
              <AlertCircle />
              <AlertDescription>{avStatus}</AlertDescription>
            </Alert>
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
                  className={`w-full h-full object-cover -scale-x-100 ${avActive ? "block" : "hidden"}`}
                />
                <canvas
                  ref={overlayCanvasRef}
                  aria-hidden="true"
                  className={`absolute inset-0 w-full h-full pointer-events-none -scale-x-100 ${avActive ? "block" : "hidden"}`}
                />
                {!avActive && (
                  <div className="text-center p-4 space-y-2 text-muted-foreground">
                    <Camera className="size-10 mx-auto opacity-40" />
                    <p className="text-xs">
                      La cámara se activa al pulsar &laquo;Activar prueba&raquo; y se libera completamente al cerrar o navegar.
                    </p>
                  </div>
                )}
                {avActive && (
                  <div className="absolute inset-0 pointer-events-none border-2 border-emerald-500/30 rounded-xl" />
                )}
              </div>
              <canvas ref={canvasRef} className="hidden" />

              {avActive && lookingAway && (
                <Alert data-testid="gaze-away" className="mt-3 border-amber-500/50 text-amber-700 dark:text-amber-400">
                  <AlertCircle />
                  <AlertDescription>
                    Mirá a la pantalla. Tu cabeza o tu mirada están fuera de la zona de pantalla; es solo un aviso, la
                    decisión es del servidor.
                  </AlertDescription>
                </Alert>
              )}
              {gazeNotice && <p className="mt-3 text-xs text-muted-foreground">{gazeNotice}</p>}

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
                        : vuLevel > 35
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
                      variant={faceCount === 1 && !presenceAlert ? "secondary" : "destructive"}
                      className="text-[11px]"
                    >
                      {cameraBlocked
                        ? "Cámara tapada o congelada"
                        : faceCovered
                        ? "Rostro cubierto"
                        : mouthCovered
                        ? "Boca cubierta"
                        : faceCount === 0
                        ? "Ausente"
                        : faceCount === 1
                        ? "1 en encuadre"
                        : `${faceCount} personas`}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {cameraBlocked
                      ? "Alerta: La cámara está tapada, sin imagen o congelada."
                      : faceCovered
                      ? "Alerta: El rostro está cubierto. Descubrilo para continuar."
                      : mouthCovered
                      ? "Alerta: La boca está cubierta. Descubrila para continuar."
                      : faceCount === 1
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
                        : headOrientation === "UP"
                        ? "Hacia arriba"
                        : headOrientation === "LEFT" || headOrientation === "RIGHT"
                        ? "Lateral"
                        : "Sin rostro"}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {headOrientation === "CENTER"
                      ? "Postura centrada mirando a pantalla."
                      : headOrientation === "DOWN"
                      ? "Alerta: Cabeza inclinada hacia abajo."
                      : headOrientation === "UP"
                      ? "Alerta: Cabeza inclinada hacia arriba."
                      : headOrientation === "LEFT" || headOrientation === "RIGHT"
                      ? "Alerta: Giro lateral pronunciado."
                      : "Esperando detección facial."}
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
                      {presenceAlert
                        ? "No verificable"
                        : identityMatch === true
                        ? "Coincide"
                        : identityMatch === false
                        ? "Discrepancia"
                        : "Pendiente"}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {presenceAlert
                      ? "El rostro no está visible por completo: no se puede cotejar."
                      : identityMatch === true
                      ? "Embedding SFace coincide con registro oficial."
                      : identityMatch === false
                      ? "Alerta: Posible suplantación a mitad de prueba."
                      : "Comparación periódica en curso."}
                  </p>
                </div>

                {/* Audio activity & mouth sync */}
                <div className="rounded-lg border p-3 bg-card space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground flex items-center gap-1.5">
                      <Volume2 className="size-3.5" /> Actividad acústica
                    </span>
                    <Badge variant={acoustic.alert ? "destructive" : "secondary"} className="text-[11px]">
                      {acoustic.label}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">{acoustic.text}</p>
                  <p data-testid="voice-status" className="text-xs text-muted-foreground">
                    Huella de voz: {trial?.voice_enrolled ? "calibrada" : "pendiente"}
                  </p>
                </div>
                {/* Eye gaze (iris) */}
                <div className="rounded-lg border p-3 bg-card space-y-1 sm:col-span-2" data-testid="iris-gaze-card">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground flex items-center gap-1.5">
                      <Eye className="size-3.5" /> Mirada (iris)
                    </span>
                    <Badge variant={irisStatus.variant} className="text-[11px]">
                      {irisStatus.label}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">{irisStatus.text}</p>
                </div>
              </div>

              <p className="text-[11px] text-muted-foreground italic border-t pt-2">
                * Orientación 3D (Pitch/Yaw) y apertura labial (jawOpen/MAR) calculadas localmente con MediaPipe Face Landmarker + Sherpa-ONNX (ventana cada 2.4s). No realiza detección de objetos/smartphones.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {avActive && active && trial && !trial.closed_at && (
        <CalibrationGate
          trial={trial}
          captureFrame={av.captureFrame}
          recorder={av.recorder}
          readMouth={av.readMouth}
          submitGaze={submitGazeCalibration}
          submitVoice={submitVoiceCalibration}
        />
      )}

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
                void session.refreshLedger().catch((cause) => session.setError(message(cause)))
              }}
            >
              Actualizar bitácora
            </Button>
            {rows.length < total && (
              <Button
                variant="outline"
                onClick={() => {
                  void session.loadMore().catch((cause) => session.setError(message(cause)))
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

      <Button
        variant="outline"
        asChild
        onClick={() => {
          if (document.fullscreenElement) void document.exitFullscreen().catch(() => undefined)
        }}
      >
        <Link to="/app/teaching-skills">Salir de la prueba</Link>
      </Button>
      </section>
    </div>
  )
}

import { useCallback, useEffect, useRef, useState } from "react"
import {
  Camera,
  CheckCircle2,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Sun,
  VideoOff,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { useProfileStore } from "@/stores/profile-store"
import { toast } from "sonner"

export function BiometricEnrollmentCard() {
  const profile = useProfileStore((state) => state.profile)
  const isEnrolling = useProfileStore((state) => state.isEnrollingBiometrics)
  const enrollBiometrics = useProfileStore((state) => state.enrollBiometrics)

  const videoRef = useRef<HTMLVideoElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const animFrameRef = useRef<number | null>(null)

  const [cameraActive, setCameraActive] = useState(false)
  const [cameraError, setCameraError] = useState<string | null>(null)
  const [lightingScore, setLightingScore] = useState<number>(0)

  // Medición continua de iluminación real leyendo píxeles del <video>
  const updateRealLighting = useCallback(() => {
    const video = videoRef.current
    if (video && video.readyState >= 2 && video.videoWidth > 0) {
      try {
        const sampleCanvas = document.createElement("canvas")
        sampleCanvas.width = 64
        sampleCanvas.height = 48
        const ctx = sampleCanvas.getContext("2d", { willReadFrequently: true })
        if (ctx) {
          ctx.drawImage(video, 0, 0, 64, 48)
          const imgData = ctx.getImageData(0, 0, 64, 48).data
          let totalLuminance = 0
          for (let i = 0; i < imgData.length; i += 4) {
            // Luminancia percibida ITU-R BT.601
            totalLuminance +=
              0.299 * imgData[i] + 0.587 * imgData[i + 1] + 0.114 * imgData[i + 2]
          }
          const avgLuminance = totalLuminance / (64 * 48)
          const scorePercent = Math.min(
            100,
            Math.max(0, Math.round((avgLuminance / 255) * 100))
          )
          setLightingScore(scorePercent)
        }
      } catch {
        // En caso de que el frame no esté listo en ese ciclo
      }
    }
    animFrameRef.current = requestAnimationFrame(updateRealLighting)
  }, [])

  const stopCamera = useCallback(() => {
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current)
      animFrameRef.current = null
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }
    setCameraActive(false)
    setCameraError(null)
    setLightingScore(0)
  }, [])

  useEffect(() => {
    return () => {
      stopCamera()
    }
  }, [stopCamera])

  const startCamera = async () => {
    setCameraError(null)
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error("Tu navegador o entorno no soporta captura de video WebRTC.")
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1280, min: 640 },
          height: { ideal: 720, min: 480 },
          facingMode: "user",
        },
        audio: false,
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
      }
      setCameraActive(true)
      // Iniciar bucle de telemetría de brillo real
      animFrameRef.current = requestAnimationFrame(updateRealLighting)
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message
          : "No se pudo acceder a la cámara web. Asegurate de otorgar permisos en el navegador."
      setCameraError(msg)
      toast.error("Error al acceder a la cámara", {
        description: msg,
      })
    }
  };

  const handleCaptureAndEnroll = async () => {
    const video = videoRef.current
    if (!video || video.readyState < 2 || video.videoWidth === 0) {
      toast.error("La cámara aún no está lista para capturar un frame.")
      return
    }

    if (lightingScore < 20) {
      toast.warning("Iluminación insuficiente", {
        description:
          "El entorno está demasiado oscuro. Mejorá la luz frontal antes de capturar.",
      })
      return
    }

    // Capturar frame nativo en resolución completa
    const canvas = document.createElement("canvas")
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const ctx = canvas.getContext("2d")
    if (!ctx) {
      toast.error("Error inicializando canvas de captura.")
      return
    }

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
    const dataUrl = canvas.toDataURL("image/jpeg", 0.95)

    const ok = await enrollBiometrics({
      image_base64: dataUrl,
      lighting_score: Number((lightingScore / 100).toFixed(2)),
      face_centered: true,
    })
    if (ok) {
      stopCamera()
    }
  }

  const isEnrolled = Boolean(profile?.has_biometric_enrollment)

  const getLightingLabel = (score: number) => {
    if (score < 25) return "Muy baja (insuficiente)"
    if (score < 50) return "Aceptable"
    if (score <= 85) return "Óptima"
    return "Intensa"
  }

  return (
    <Card className="border-border/80 shadow-2xs">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2 text-lg">
              <ShieldCheck className="size-5 text-primary" />
              Enrolamiento Biométrico Facial (Rostro Testigo)
            </CardTitle>
            <CardDescription>
              Registrá tu rostro testigo oficial procesado localmente con redes neuronales OpenCV (YuNet + SFace, 128-d). Se utilizará para verificar tu identidad durante las evaluaciones supervisadas de habilidades.
            </CardDescription>
          </div>
          {isEnrolled ? (
            <Badge className="bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30 gap-1.5 px-3 py-1">
              <CheckCircle2 className="size-3.5" />
              Rostro Testigo Vinculado
            </Badge>
          ) : (
            <Badge variant="outline" className="border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300 gap-1.5 px-3 py-1">
              <ShieldAlert className="size-3.5" />
              Pendiente de Enrolamiento
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {isEnrolled && profile?.biometric_face_hash && (
          <div className="rounded-lg border border-emerald-500/25 bg-emerald-500/5 p-3.5 text-xs space-y-1.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-semibold text-foreground flex items-center gap-1.5">
                <Sparkles className="size-3.5 text-primary" />
                Vector Biométrico Local Activo ({profile.embedding_dimensions ?? 128} dimensiones)
              </span>
              {profile.biometric_enrolled_at && (
                <span className="text-muted-foreground">
                  Registrado: {new Date(profile.biometric_enrolled_at).toLocaleString()}
                </span>
              )}
            </div>
            <p className="font-mono text-[11px] text-muted-foreground break-all">
              Firma SHA-256: {profile.biometric_face_hash}
            </p>
          </div>
        )}

        {cameraError && (
          <div className="flex items-center gap-3 rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-xs text-destructive">
            <VideoOff className="size-5 shrink-0" />
            <div>
              <p className="font-semibold">No se pudo acceder a la cámara</p>
              <p className="text-muted-foreground mt-0.5">{cameraError}</p>
            </div>
          </div>
        )}

        {!cameraActive ? (
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 rounded-xl border bg-muted/30 p-4">
            <div className="space-y-1 text-sm">
              <p className="font-medium text-foreground">
                {isEnrolled
                  ? "¿Deseás recalibrar tu rostro testigo oficial?"
                  : "Activá tu cámara para realizar el enrolamiento biométrico"}
              </p>
              <p className="text-xs text-muted-foreground">
                El descriptor facial se extrae en memoria. No se almacenan fotografías crudas ni se transmiten datos a servicios externos.
              </p>
            </div>
            <Button onClick={startCamera} className="shrink-0 gap-2">
              <Camera className="size-4" />
              {isEnrolled ? "Recalibrar Rostro Testigo" : "Iniciar Cámara"}
            </Button>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-5">
            {/* Visor con Guía Oval de Encuadre */}
            <div className="relative overflow-hidden rounded-xl border bg-slate-950 aspect-video md:col-span-3 flex items-center justify-center">
              <video
                ref={videoRef}
                muted
                playsInline
                className="h-full w-full object-cover"
              />

              {/* Guía Oval Superpuesta de Encuadre */}
              <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                <div
                  className={`h-48 w-36 sm:h-56 sm:w-44 rounded-full border-2 border-dashed transition-colors ${
                    lightingScore >= 25
                      ? "border-emerald-400 shadow-[0_0_25px_rgba(16,185,129,0.35)]"
                      : "border-amber-400"
                  }`}
                />
              </div>

              <div className="absolute bottom-2.5 left-3 right-3 flex items-center justify-between text-[11px] text-white/90 bg-black/60 backdrop-blur-xs rounded-md px-2.5 py-1">
                <span>Guía oval frontal</span>
                <span className={lightingScore >= 25 ? "font-semibold text-emerald-400" : "font-semibold text-amber-400"}>
                  {lightingScore >= 25 ? "Encuadre listo" : "Ajustá la iluminación"}
                </span>
              </div>
            </div>

            {/* Panel de Telemetría de Iluminación y Controles */}
            <div className="flex flex-col justify-between rounded-xl border bg-card p-4 space-y-4 md:col-span-2">
              <div className="space-y-4">
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium flex items-center gap-1.5">
                      <Sun className="size-3.5 text-primary" />
                      Iluminación en vivo
                    </span>
                    <span className="font-semibold text-foreground">
                      {lightingScore}% ({getLightingLabel(lightingScore)})
                    </span>
                  </div>
                  <Progress value={lightingScore} className="h-2" />
                </div>

                <div className="rounded-lg border bg-muted/20 p-3 space-y-1.5 text-xs text-muted-foreground leading-relaxed">
                  <p className="font-medium text-foreground">Instrucciones de captura:</p>
                  <ul className="list-disc pl-4 space-y-1 text-[11px]">
                    <li>Mirá fijamente a la cámara con expresión neutra.</li>
                    <li>Ubicá tu rostro en el centro del óvalo.</li>
                    <li>Asegurate de estar solo frente a la pantalla.</li>
                    <li>Evitá contraluces y brillos excesivos.</li>
                  </ul>
                </div>
              </div>

              <div className="flex flex-col gap-2 pt-2">
                <Button
                  onClick={handleCaptureAndEnroll}
                  disabled={isEnrolling || lightingScore < 20}
                  className="w-full gap-2"
                >
                  {isEnrolling ? (
                    <>
                      <RefreshCw className="size-4 animate-spin" />
                      Extrayendo Características...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="size-4" />
                      Capturar y Vincular Rostro
                    </>
                  )}
                </Button>
                <Button
                  variant="outline"
                  onClick={stopCamera}
                  disabled={isEnrolling}
                  className="w-full"
                >
                  Cancelar
                </Button>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

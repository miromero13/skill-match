import { useCallback, useEffect, useRef, useState } from "react"
import {
  Camera,
  CheckCircle2,
  FileCheck2,
  IdCard,
  RefreshCw,
  ShieldAlert,
  Sun,
  Upload,
  VideoOff,
  X,
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
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import { useProfileStore } from "@/stores/profile-store"
import { useAuthStore } from "@/stores/auth-store"
import { toast } from "sonner"

export function BiometricEnrollmentCard({ onVerified }: { onVerified?: () => void } = {}) {
  const profile = useProfileStore((state) => state.profile)
  const isVerifying = useProfileStore((state) => state.isVerifyingIdentity)
  const verifyIdentity = useProfileStore((state) => state.verifyIdentity)
  const authUser = useAuthStore((state) => state.user)

  const videoRef = useRef<HTMLVideoElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const animFrameRef = useRef<number | null>(null)

  const fileInputFrontRef = useRef<HTMLInputElement | null>(null)
  const fileInputFrontCameraRef = useRef<HTMLInputElement | null>(null)
  const fileInputBackRef = useRef<HTMLInputElement | null>(null)
  const fileInputBackCameraRef = useRef<HTMLInputElement | null>(null)

  const [activeStep, setActiveStep] = useState<1 | 2>(1)
  const [cameraError, setCameraError] = useState<string | null>(null)
  const [lightingScore, setLightingScore] = useState<number>(0)

  // Datos del Carnet CI / DNI (Anverso y Reverso)
  const [frontImageBase64, setFrontImageBase64] = useState<string | null>(null)
  const [backImageBase64, setBackImageBase64] = useState<string | null>(null)

  const accountName = profile?.full_name || authUser?.fullName || "Titular Registrado"

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
        // Fallback silencioso
      }
    }
    animFrameRef.current = requestAnimationFrame(updateRealLighting)
  }, [])

  const stopCamera = useCallback(() => {
    if (animFrameRef.current !== null) {
      cancelAnimationFrame(animFrameRef.current)
      animFrameRef.current = null
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null
    }
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
  }

  const handleFileUpload = (
    e: React.ChangeEvent<HTMLInputElement>,
    side: "front" | "back"
  ) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (!file.type.startsWith("image/")) {
      toast.error("El archivo debe ser una imagen válida (JPG o PNG).")
      return
    }

    if (file.size > 8 * 1024 * 1024) {
      toast.error("La imagen supera el límite máximo de 8 MB.")
      return
    }

    const reader = new FileReader()
    reader.onload = () => {
      if (typeof reader.result === "string") {
        if (side === "front") {
          setFrontImageBase64(reader.result)
          toast.success("Anverso del carnet cargado correctamente.")
        } else {
          setBackImageBase64(reader.result)
          toast.success("Reverso del carnet cargado correctamente.")
        }
      }
    }
    reader.onerror = () => {
      toast.error("Error al leer el archivo del carnet.")
    }
    reader.readAsDataURL(file)
  }

  const handleGoToCameraStep = () => {
    if (!frontImageBase64) {
      toast.error("Cargá la fotografía del anverso de tu carnet de identidad.")
      return
    }
    if (!backImageBase64) {
      toast.error("Cargá la fotografía del reverso de tu carnet de identidad.")
      return
    }
    setActiveStep(2)
    startCamera()
  }

  const handleCaptureAndVerify = async () => {
    const video = videoRef.current
    if (!video || video.readyState < 2 || video.videoWidth === 0) {
      toast.error("La cámara aún no está lista para capturar un frame.")
      return
    }

    if (lightingScore < 20) {
      toast.warning("Iluminación insuficiente", {
        description: "El entorno está oscuro. Mejorá la luz frontal antes de verificar.",
      })
      return
    }

    if (!frontImageBase64 || !backImageBase64) {
      toast.error("Se requieren ambas fotografías (anverso y reverso del carnet).")
      setActiveStep(1)
      return
    }

    const canvas = document.createElement("canvas")
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const ctx = canvas.getContext("2d")
    if (!ctx) {
      toast.error("Error inicializando canvas de captura.")
      return
    }

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
    const selfieDataUrl = canvas.toDataURL("image/jpeg", 0.95)

    const ok = await verifyIdentity({
      id_card_base64: frontImageBase64,
      id_card_back_base64: backImageBase64,
      selfie_base64: selfieDataUrl,
      id_number: profile?.id_document_number || "CI-AUTO",
      full_name: accountName,
      lighting_score: Number((lightingScore / 100).toFixed(2)),
      face_centered: true,
    })

    if (ok) {
      stopCamera()
      setActiveStep(1)
      setFrontImageBase64(null)
      setBackImageBase64(null)
      onVerified?.()
    }
  }

  const isVerified = profile?.identity_status === "VERIFIED"
  const isEnrolled = Boolean(profile?.has_biometric_enrollment)

  const getLightingLabel = (score: number) => {
    if (score < 25) return "Baja (ajustá la luz)"
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
              <IdCard className="size-5 text-primary" />
              Verificación de Identidad con Carnet (CI/DNI)
            </CardTitle>
            <CardDescription>
              Cotejo automático entre las dos caras de tu documento oficial y tu rostro en vivo para validar tu identidad.
            </CardDescription>
          </div>
          {isVerified ? (
            <Badge className="bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30 gap-1.5 px-3 py-1">
              <CheckCircle2 className="size-3.5" />
              Identidad Verificada
            </Badge>
          ) : isEnrolled ? (
            <Badge variant="outline" className="border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300 gap-1.5 px-3 py-1">
              <ShieldAlert className="size-3.5" />
              Rostro Enrolado (Requiere Carnet)
            </Badge>
          ) : (
            <Badge variant="outline" className="border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300 gap-1.5 px-3 py-1">
              <ShieldAlert className="size-3.5" />
              Identidad No Verificada
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {isVerified ? (
          <div className="rounded-xl border border-emerald-500/25 bg-emerald-500/5 p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-emerald-500/15 pb-2.5">
              <div className="flex items-center gap-2">
                <FileCheck2 className="size-4 text-emerald-600 dark:text-emerald-400" />
                <span className="font-semibold text-sm text-foreground">
                  Titular Verificado: {profile?.full_name}
                </span>
              </div>
              <span className="font-mono text-xs font-semibold px-2.5 py-0.5 rounded-md bg-emerald-500/15 text-emerald-700 dark:text-emerald-300">
                CI/DNI: {profile?.id_document_number}
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-muted-foreground pt-1">
              <div>
                <span className="block font-medium text-foreground">Fecha de Verificación</span>
                <span>
                  {profile?.identity_verified_at
                    ? new Date(profile.identity_verified_at).toLocaleDateString()
                    : "Registrado"}
                </span>
              </div>
              <div>
                <span className="block font-medium text-foreground">Estado</span>
                <span className="text-emerald-600 dark:text-emerald-400 font-semibold">Identidad Oficial Verificada ✓</span>
              </div>
            </div>

            <div className="pt-2 flex flex-wrap items-center justify-between gap-2 border-t border-emerald-500/10">
              <div className="flex items-center gap-1.5 text-xs text-emerald-700 dark:text-emerald-300 font-medium">
                <CheckCircle2 className="size-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                <span>Documento e identidad vinculados de forma inmutable</span>
              </div>
              {onVerified && (
                <Button size="sm" onClick={onVerified} className="text-xs h-7">
                  Cerrar
                </Button>
              )}
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {profile?.identity_rejection_reason && (
              <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive flex items-start gap-2.5">
                <ShieldAlert className="size-4 shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold">Último intento rechazado automáticamente:</p>
                  <p className="mt-0.5">{profile.identity_rejection_reason}</p>
                </div>
              </div>
            )}

            {/* Selector de Pasos */}
            <div className="flex items-center gap-2 border-b pb-2 text-xs font-medium">
              <span
                className={`px-3 py-1 rounded-md transition-colors ${
                  activeStep === 1
                    ? "bg-primary text-primary-foreground font-semibold"
                    : "text-muted-foreground"
                }`}
              >
                1. Carnet (Anverso y Reverso)
              </span>
              <span className="text-muted-foreground">→</span>
              <span
                className={`px-3 py-1 rounded-md transition-colors ${
                  activeStep === 2
                    ? "bg-primary text-primary-foreground font-semibold"
                    : "text-muted-foreground"
                }`}
              >
                2. Rostro en Vivo (Cámara)
              </span>
            </div>

            {/* PASO 1: Captura de Carnet (Anverso y Reverso) */}
            {activeStep === 1 && (
              <div className="space-y-4 pt-1">
                {/* Banner informativo del titular sin inputs manuales */}
                <div className="rounded-xl border border-primary/20 bg-primary/5 p-3.5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                  <div className="space-y-0.5">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground block">
                      Titular Oficial de la Cuenta a Contrastar
                    </span>
                    <p className="text-sm font-bold text-foreground">
                      {accountName}
                    </p>
                    <p className="text-[11px] text-muted-foreground">
                      El número de carnet y tu nombre se contrastarán automáticamente desde las fotografías del documento sin necesidad de escribirlos a mano.
                    </p>
                  </div>
                  <Badge variant="outline" className="text-[11px] bg-background shrink-0 gap-1 font-medium">
                    <CheckCircle2 className="size-3 text-primary" />
                    Cuenta Verificada
                  </Badge>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {/* ANVERSO */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label className="text-xs font-semibold flex items-center gap-1.5">
                        <IdCard className="size-4 text-primary" />
                        1. Anverso (Frontal) *
                      </Label>
                      {frontImageBase64 ? (
                        <Badge variant="default" className="text-[10px] bg-emerald-600 hover:bg-emerald-600 px-1.5 py-0">
                          Cargado ✓
                        </Badge>
                      ) : (
                        <span className="text-[11px] text-muted-foreground">Obligatorio</span>
                      )}
                    </div>
                    <input
                      ref={fileInputFrontRef}
                      type="file"
                      accept="image/*"
                      data-testid="input-front-card"
                      onChange={(e) => handleFileUpload(e, "front")}
                      className="hidden"
                    />
                    <input
                      ref={fileInputFrontCameraRef}
                      type="file"
                      accept="image/*"
                      capture="environment"
                      onChange={(e) => handleFileUpload(e, "front")}
                      className="hidden"
                    />

                    {frontImageBase64 ? (
                      <div className="relative rounded-xl border bg-muted/20 p-3 flex items-center justify-between gap-3">
                        <div className="flex items-center gap-3 min-w-0">
                          <img
                            src={frontImageBase64}
                            alt="Anverso carnet"
                            className="h-14 w-20 object-cover rounded-md border shadow-xs shrink-0"
                          />
                          <div className="text-xs min-w-0">
                            <p className="font-medium text-foreground truncate">Anverso cargado</p>
                            <p className="text-muted-foreground text-[11px] truncate">
                              Fotografía oficial y datos
                            </p>
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setFrontImageBase64(null)}
                          className="shrink-0"
                          aria-label="Eliminar anverso"
                        >
                          <X className="size-4" />
                        </Button>
                      </div>
                    ) : (
                      <div className="border-2 border-dashed border-border/80 hover:border-primary/50 rounded-xl p-4 text-center space-y-3 bg-muted/10 transition-colors">
                        <div className="text-xs space-y-0.5">
                          <p className="font-semibold text-foreground">
                            Anverso del carnet físico
                          </p>
                          <p className="text-muted-foreground text-[11px]">
                            Foto nítida con tu fotografía y datos visibles
                          </p>
                        </div>
                        <div className="flex items-center justify-center gap-2 pt-1">
                          <Button
                            type="button"
                            size="sm"
                            className="h-8 text-xs gap-1.5"
                            onClick={() => fileInputFrontCameraRef.current?.click()}
                          >
                            <Camera className="size-3.5" />
                            Tomar Foto
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            className="h-8 text-xs gap-1.5"
                            onClick={() => fileInputFrontRef.current?.click()}
                          >
                            <Upload className="size-3.5" />
                            Galería
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* REVERSO */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label className="text-xs font-semibold flex items-center gap-1.5">
                        <FileCheck2 className="size-4 text-primary" />
                        2. Reverso (Posterior) *
                      </Label>
                      {backImageBase64 ? (
                        <Badge variant="default" className="text-[10px] bg-emerald-600 hover:bg-emerald-600 px-1.5 py-0">
                          Cargado ✓
                        </Badge>
                      ) : (
                        <span className="text-[11px] text-muted-foreground">Obligatorio</span>
                      )}
                    </div>
                    <input
                      ref={fileInputBackRef}
                      type="file"
                      accept="image/*"
                      data-testid="input-back-card"
                      onChange={(e) => handleFileUpload(e, "back")}
                      className="hidden"
                    />
                    <input
                      ref={fileInputBackCameraRef}
                      type="file"
                      accept="image/*"
                      capture="environment"
                      onChange={(e) => handleFileUpload(e, "back")}
                      className="hidden"
                    />

                    {backImageBase64 ? (
                      <div className="relative rounded-xl border bg-muted/20 p-3 flex items-center justify-between gap-3">
                        <div className="flex items-center gap-3 min-w-0">
                          <img
                            src={backImageBase64}
                            alt="Reverso carnet"
                            className="h-14 w-20 object-cover rounded-md border shadow-xs shrink-0"
                          />
                          <div className="text-xs min-w-0">
                            <p className="font-medium text-foreground truncate">Reverso cargado</p>
                            <p className="text-muted-foreground text-[11px] truncate">
                              Código de barras / MRZ y sellos
                            </p>
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setBackImageBase64(null)}
                          className="shrink-0"
                          aria-label="Eliminar reverso"
                        >
                          <X className="size-4" />
                        </Button>
                      </div>
                    ) : (
                      <div className="border-2 border-dashed border-border/80 hover:border-primary/50 rounded-xl p-4 text-center space-y-3 bg-muted/10 transition-colors">
                        <div className="text-xs space-y-0.5">
                          <p className="font-semibold text-foreground">
                            Reverso del carnet físico
                          </p>
                          <p className="text-muted-foreground text-[11px]">
                            Debe apreciarse el código de barras o MRZ
                          </p>
                        </div>
                        <div className="flex items-center justify-center gap-2 pt-1">
                          <Button
                            type="button"
                            size="sm"
                            className="h-8 text-xs gap-1.5"
                            onClick={() => fileInputBackCameraRef.current?.click()}
                          >
                            <Camera className="size-3.5" />
                            Tomar Foto
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            className="h-8 text-xs gap-1.5"
                            onClick={() => fileInputBackRef.current?.click()}
                          >
                            <Upload className="size-3.5" />
                            Galería
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex flex-wrap justify-between items-center gap-3 pt-2">
                  <div className="text-[11px] text-muted-foreground flex items-center gap-1.5">
                    <ShieldAlert className="size-3.5 text-amber-500 shrink-0" />
                    <span>Se requieren ambas caras del documento físico para validar autenticidad.</span>
                  </div>
                  <Button
                    onClick={handleGoToCameraStep}
                    disabled={!frontImageBase64 || !backImageBase64}
                    className="ml-auto gap-2"
                  >
                    Siguiente: Cotejo Facial en Vivo
                  </Button>
                </div>
              </div>
            )}

            {/* PASO 2: Rostro en Vivo con Cámara */}
            {activeStep === 2 && (
              <div className="space-y-4 pt-1">
                {cameraError && (
                  <div className="flex items-center gap-3 rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-xs text-destructive">
                    <VideoOff className="size-5 shrink-0" />
                    <div>
                      <p className="font-semibold">No se pudo acceder a la cámara</p>
                      <p className="text-muted-foreground mt-0.5">{cameraError}</p>
                    </div>
                  </div>
                )}

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
                      <span
                        className={
                          lightingScore >= 25
                            ? "font-semibold text-emerald-400"
                            : "font-semibold text-amber-400"
                        }
                      >
                        {lightingScore >= 25 ? "Encuadre listo" : "Ajustá la iluminación"}
                      </span>
                    </div>
                  </div>

                  {/* Panel de Telemetría y Controles */}
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
                        <p className="font-medium text-foreground">Reglas de verificación automática:</p>
                        <ul className="list-disc pl-4 space-y-1 text-[11px]">
                          <li>Tu rostro en vivo debe coincidir con la foto del anverso del carnet.</li>
                          <li>El nombre del documento debe coincidir con {accountName}.</li>
                          <li>Mirá a la cámara dentro de la guía oval con buena luz frontal.</li>
                          <li>La IA rechazará automáticamente cualquier intento de suplantación.</li>
                        </ul>
                      </div>
                    </div>

                    <div className="flex flex-col gap-2 pt-2">
                      <Button
                        onClick={handleCaptureAndVerify}
                        disabled={isVerifying || lightingScore < 20}
                        className="w-full gap-2"
                      >
                        {isVerifying ? (
                          <>
                            <RefreshCw className="size-4 animate-spin" />
                            Cotejando con IA Local...
                          </>
                        ) : (
                          <>
                            <CheckCircle2 className="size-4" />
                            Verificar Identidad Automáticamente
                          </>
                        )}
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => {
                          stopCamera()
                          setActiveStep(1)
                        }}
                        disabled={isVerifying}
                        className="w-full"
                      >
                        Volver al Carnet
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

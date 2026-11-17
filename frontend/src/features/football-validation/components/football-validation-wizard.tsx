import { useEffect, useReducer, useRef, useState } from "react"
import {
  Camera,
  CheckCircle2,
  CloudUpload,
  Eye,
  Play,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Square,
  Volume2,
  Sun,
  Crosshair,
  AlertCircle,
} from "lucide-react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Input } from "@/components/ui/input"
import {
  footballValidationReducer,
  initialFootballValidationState,
  type ValidationResultPayload,
} from "../state/football-session-machine"
import {
  computeBlobSha256Hex,
  footballValidationApi,
} from "../api/football-validation-api"
import { useMediaCapture } from "../hooks/use-media-capture"
import { useChunkUploader } from "../hooks/use-chunk-uploader"
import { useChallengeSocket } from "../hooks/use-challenge-socket"
import { usePageVisibility } from "../hooks/use-page-visibility"
import { ChallengeHud } from "./challenge-hud"
import { FootballResultView } from "./football-result-view"

type WizardStep =
  | "intro"
  | "env_check"
  | "liveness"
  | "calibration"
  | "recording"
  | "processing"
  | "result"

interface FootballValidationWizardProps {
  skillId?: string
}

export function FootballValidationWizard({
  skillId,
}: FootballValidationWizardProps = {}) {
  const [machine, dispatch] = useReducer(
    footballValidationReducer,
    initialFootballValidationState
  )
  const [step, setStep] = useState<WizardStep>("intro")
  const [consentChecked, setConsentChecked] = useState(false)
  const [isBusy, setIsBusy] = useState(false)

  // Live environment telemetry (canvas luminance + Web Audio AnalyserNode)
  const [measuredBrightness, setMeasuredBrightness] = useState<number>(125)
  const [measuredNoiseDb, setMeasuredNoiseDb] = useState<number>(42)
  const [faceDetected, setFaceDetected] = useState<boolean>(true)
  const [ballDetected, setBallDetected] = useState<boolean>(true)

  // Live challenge recording state
  const [activeSegmentIdx, setActiveSegmentIdx] = useState<number>(0)
  const [segmentRemainingSec, setSegmentRemainingSec] = useState<number>(8)
  const [approxTouches, setApproxTouches] = useState<number>(0)
  const [finalResult, setFinalResult] =
    useState<ValidationResultPayload | null>(null)

  const videoRef = useRef<HTMLVideoElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  const {
    confirmedChunks,
    isUploading: isChunkUploading,
    uploadError,
    enqueueChunk,
    resumePendingChunks,
    resetUploader,
  } = useChunkUploader(machine.sessionId, {}, (chunkResp) => {
    dispatch({
      type: "CHUNK_CONFIRMED",
      payload: {
        chunkIndex: chunkResp.chunk_index,
        estado: chunkResp.estado,
      },
    })
  })

  const {
    stream,
    isRecording,
    elapsedSeconds,
    error: captureError,
    requestPermissionsAndStream,
    startRecording,
    stopRecording,
    releaseStream,
  } = useMediaCapture({
    chunkDurationMs: 5000,
    onChunkAvailable: (idx, blob) => {
      void enqueueChunk(idx, blob)
    },
  })

  const { activeCommand, sendClientEvent } = useChallengeSocket(machine.wsUrl)

  usePageVisibility(step === "recording", (evt) => {
    sendClientEvent(evt)
  })

  // Attach live camera stream to <video> element
  useEffect(() => {
    if (videoRef.current && stream) {
      videoRef.current.srcObject = stream
    }
  }, [stream, step])

  // Sample real brightness from <canvas> and noise level from Web Audio API during env_check
  useEffect(() => {
    if (step !== "env_check" || !stream) return

    let audioCtx: AudioContext | null = null
    let analyser: AnalyserNode | null = null
    const audioTracks = stream.getAudioTracks()
    if (
      audioTracks.length > 0 &&
      typeof window !== "undefined" &&
      "AudioContext" in window
    ) {
      try {
        audioCtx = new window.AudioContext()
        const source = audioCtx.createMediaStreamSource(stream)
        analyser = audioCtx.createAnalyser()
        analyser.fftSize = 256
        source.connect(analyser)
      } catch {
        audioCtx = null
      }
    }

    const interval = window.setInterval(() => {
      if (videoRef.current && canvasRef.current) {
        const ctx = canvasRef.current.getContext("2d")
        if (ctx && videoRef.current.videoWidth > 0) {
          canvasRef.current.width = 64
          canvasRef.current.height = 36
          ctx.drawImage(videoRef.current, 0, 0, 64, 36)
          const pixels = ctx.getImageData(0, 0, 64, 36).data
          let sum = 0
          for (let i = 0; i < pixels.length; i += 4) {
            sum += 0.299 * pixels[i] + 0.587 * pixels[i + 1] + 0.114 * pixels[i + 2]
          }
          const avgLum = Math.round(sum / (pixels.length / 4))
          if (avgLum > 0) {
            setMeasuredBrightness(avgLum)
          }
        }
      }

      if (analyser) {
        const dataArr = new Uint8Array(analyser.frequencyBinCount)
        analyser.getByteFrequencyData(dataArr)
        const avg =
          dataArr.reduce((acc, v) => acc + v, 0) /
          Math.max(1, dataArr.length)
        const estimatedDb = Math.min(95, Math.max(25, Math.round(25 + avg * 0.45)))
        setMeasuredNoiseDb(estimatedDb)
      }
    }, 600)

    return () => {
      window.clearInterval(interval)
      if (audioCtx) {
        void audioCtx.close()
      }
    }
  }, [step, stream])

  // Rotate through planned challenge segments during live recording
  useEffect(() => {
    if (step !== "recording" || machine.segments.length === 0) return

    const timer = window.setInterval(() => {
      setSegmentRemainingSec((prev) => {
        if (prev <= 1) {
          setActiveSegmentIdx((idx) => {
            const nextIdx = idx + 1 < machine.segments.length ? idx + 1 : idx
            const nextSeg = machine.segments[nextIdx] ?? machine.segments[0]
            window.setTimeout(() => {
              setSegmentRemainingSec(Math.round(nextSeg.duracion_ms / 1000))
            }, 0)
            return nextIdx
          })
          return 8
        }
        return prev - 1
      })
    }, 1000)

    return () => window.clearInterval(timer)
  }, [step, machine.segments])

  const handleStartSession = async () => {
    if (!consentChecked) return
    setIsBusy(true)
    dispatch({ type: "SET_ERROR", payload: null })
    try {
      const created = await footballValidationApi.createSession(skillId)
      dispatch({ type: "SESSION_CREATED", payload: created.data })
      const statusRes = await footballValidationApi.getSessionStatus(
        created.data.session_id
      )
      dispatch({ type: "STATUS_SYNCED", payload: statusRes.data })

      try {
        await requestPermissionsAndStream()
      } catch {
        // Allow continuing in desktop/testing mode even without physical webcam
      }
      setStep("env_check")
    } catch (err) {
      dispatch({
        type: "SET_ERROR",
        payload:
          err instanceof Error
            ? err.message
            : "No se pudo crear la sesión de validación.",
      })
    } finally {
      setIsBusy(false)
    }
  }

  const handleSubmitEnvCheck = async () => {
    if (!machine.sessionId) return
    setIsBusy(true)
    try {
      const res = await footballValidationApi.submitEnvCheck(
        machine.sessionId,
        {
          brightness: measuredBrightness,
          noise_db: measuredNoiseDb,
          face_detected: faceDetected,
          ball_detected: ballDetected,
          latency_ms: 42,
        }
      )
      dispatch({ type: "ENV_CHECK_UPDATED", payload: res.data })
      if (res.data.passed) {
        setStep("liveness")
      }
    } catch (err) {
      dispatch({
        type: "SET_ERROR",
        payload:
          err instanceof Error ? err.message : "Error en chequeo de ambiente.",
      })
    } finally {
      setIsBusy(false)
    }
  }

  const handleSubmitLiveness = async () => {
    if (!machine.sessionId) return
    setIsBusy(true)
    try {
      const res = await footballValidationApi.submitLiveness(
        machine.sessionId,
        {
          challenge_passed: true,
          gesture_code: "head_nod",
          confidence: 0.96,
        }
      )
      dispatch({
        type: "STATE_UPDATED",
        payload: { estado: res.data.estado },
      })
      setStep("calibration")
    } catch (err) {
      dispatch({
        type: "SET_ERROR",
        payload:
          err instanceof Error ? err.message : "Error en prueba de vida.",
      })
    } finally {
      setIsBusy(false)
    }
  }

  const handleConfirmCalibrationAndRecord = async () => {
    if (!machine.sessionId) return
    setIsBusy(true)
    try {
      const res = await footballValidationApi.submitCalibration(
        machine.sessionId,
        {
          client_touch_timestamp_ms: 1000,
          estimated_ball_radius_px: 26.0,
        }
      )
      dispatch({
        type: "STATE_UPDATED",
        payload: { estado: res.data.estado },
      })
      setActiveSegmentIdx(0)
      setApproxTouches(0)
      setStep("recording")
      if (stream) {
        await startRecording()
      }
    } catch (err) {
      dispatch({
        type: "SET_ERROR",
        payload:
          err instanceof Error ? err.message : "Error en calibración.",
      })
    } finally {
      setIsBusy(false)
    }
  }

  const handleFinishRecordingAndScore = async () => {
    if (!machine.sessionId) return
    setIsBusy(true)
    stopRecording()
    setStep("processing")

    try {
      await resumePendingChunks()
      const finRes = await footballValidationApi.finalizeSession(
        machine.sessionId,
        {
          duration_seconds: Math.max(5, elapsedSeconds || 20),
          fps: 30,
        }
      )
      dispatch({ type: "SESSION_FINALIZED", payload: finRes.data })

      const resultRes = await footballValidationApi.getSessionResult(
        machine.sessionId
      )
      setFinalResult(resultRes.data)
      releaseStream()
      setStep("result")
    } catch (err) {
      dispatch({
        type: "SET_ERROR",
        payload:
          err instanceof Error
            ? err.message
            : "Error al ensamblar o evaluar los fragmentos.",
      })
      setStep("recording")
    } finally {
      setIsBusy(false)
    }
  }

  const handleUploadPreRecordedVideoForValidation = async (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0]
    if (!file || !machine.sessionId) return

    setIsBusy(true)
    dispatch({ type: "SET_ERROR", payload: null })
    setStep("processing")

    try {
      // Slice file into 5-parts (or 1 chunk if small) and upload each to Garage S3 via PUT /chunks/{n}
      const totalParts = Math.min(8, Math.max(1, Math.ceil(file.size / (256 * 1024))))
      const partSize = Math.ceil(file.size / totalParts)

      for (let i = 0; i < totalParts; i++) {
        const slice = file.slice(
          i * partSize,
          Math.min(file.size, (i + 1) * partSize),
          file.type || "video/mp4"
        )
        const sha = await computeBlobSha256Hex(slice)
        const up = await footballValidationApi.uploadChunk(
          machine.sessionId,
          i,
          slice,
          sha
        )
        dispatch({
          type: "CHUNK_CONFIRMED",
          payload: { chunkIndex: i, estado: up.data.estado },
        })
      }

      const finRes = await footballValidationApi.finalizeSession(
        machine.sessionId,
        {
          expected_chunks: totalParts,
          duration_seconds: totalParts * 5,
          fps: 30,
        }
      )
      dispatch({ type: "SESSION_FINALIZED", payload: finRes.data })

      const resultRes = await footballValidationApi.getSessionResult(
        machine.sessionId
      )
      setFinalResult(resultRes.data)
      releaseStream()
      setStep("result")
    } catch (err) {
      dispatch({
        type: "SET_ERROR",
        payload:
          err instanceof Error
            ? err.message
            : "Error procesando archivo de video.",
      })
      setStep("recording")
    } finally {
      setIsBusy(false)
    }
  }

  const handleResetAll = () => {
    releaseStream()
    resetUploader()
    setFinalResult(null)
    dispatch({ type: "RESET" })
    setStep("intro")
  }

  const currentPlannedCommand =
    activeCommand ??
    machine.segments[activeSegmentIdx] ??
    machine.segments[0] ??
    null

  return (
    <div className="space-y-6" data-testid="football-validation-wizard">
      {/* Barra de Progreso de Pantallas (Sección 9) */}
      <div className="flex flex-wrap items-center gap-2">
        {(
          [
            ["intro", "1. Consentimiento"],
            ["env_check", "2. Ambiente"],
            ["liveness", "3. Prueba de Vida"],
            ["calibration", "4. Calibración"],
            ["recording", "5. Retos en Vivo"],
            ["processing", "6. Procesando"],
            ["result", "7. Resultado"],
          ] as const
        ).map(([key, label]) => (
          <Badge
            key={key}
            variant={step === key ? "default" : "outline"}
            className="text-xs"
          >
            {label}
          </Badge>
        ))}
        {machine.sessionId && (
          <Badge variant="secondary" className="ml-auto font-mono text-[11px]">
            Sesión: {machine.sessionId.slice(0, 8)} • Estado:{" "}
            {machine.serverState}
          </Badge>
        )}
      </div>

      {(machine.errorMessage || captureError || uploadError) && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Aviso del Validador</AlertTitle>
          <AlertDescription className="text-xs">
            {machine.errorMessage || captureError || uploadError}
          </AlertDescription>
        </Alert>
      )}

      {/* Paso 1: Intro y Consentimiento */}
      {step === "intro" && (
        <Card className="border-border/70 shadow-sm">
          <CardHeader>
            <CardTitle className="text-xl font-bold flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-emerald-500" />
              Validación de Habilidad de Fútbol
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-start gap-3 p-4 rounded-lg border border-emerald-500/30 bg-emerald-500/5">
              <Switch
                id="football-consent-switch"
                checked={consentChecked}
                onCheckedChange={setConsentChecked}
              />
              <div className="space-y-1">
                <Label
                  htmlFor="football-consent-switch"
                  className="text-xs font-semibold cursor-pointer"
                >
                  Consentimiento de grabación y supervisión antifraude
                </Label>
                <p className="text-xs text-muted-foreground">
                  Uso de cámara y micrófono, con retención máxima de 30 días.
                </p>
              </div>
            </div>

            <Button
              type="button"
              onClick={handleStartSession}
              disabled={!consentChecked || isBusy}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
              data-testid="start-football-session-btn"
            >
              <Play className="w-4 h-4 mr-2" />
              {isBusy ? "Creando sesión..." : "Iniciar Validación"}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Paso 2: Verificación de Ambiente */}
      {step === "env_check" && (
        <Card className="border-border/70 shadow-sm">
          <CardHeader>
            <CardTitle className="text-lg font-semibold flex items-center gap-2">
              <Sun className="w-5 h-5 text-amber-500" />
              Verificación de Ambiente
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <canvas ref={canvasRef} className="hidden" />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="relative aspect-video rounded-lg overflow-hidden bg-neutral-950 border border-border flex items-center justify-center">
                {stream ? (
                  <video
                    ref={videoRef}
                    autoPlay
                    muted
                    playsInline
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="text-center p-4 text-xs text-muted-foreground">
                    <Camera className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    Sin cámara detectada.
                  </div>
                )}
              </div>

              <div className="space-y-3">
                <div className="space-y-1">
                  <Label className="text-xs flex items-center justify-between">
                    <span>Luz Media (umbral 40–245):</span>
                    <span className="font-mono font-bold">
                      {measuredBrightness} / 255
                    </span>
                  </Label>
                  <Input
                    type="number"
                    min={0}
                    max={255}
                    value={measuredBrightness}
                    onChange={(e) =>
                      setMeasuredBrightness(Number(e.target.value))
                    }
                  />
                </div>

                <div className="space-y-1">
                  <Label className="text-xs flex items-center justify-between">
                    <span className="flex items-center gap-1">
                      <Volume2 className="w-3.5 h-3.5" /> Ruido Ambiental (máx 75 dB):
                    </span>
                    <span className="font-mono font-bold">
                      {measuredNoiseDb} dB
                    </span>
                  </Label>
                  <Input
                    type="number"
                    min={0}
                    max={120}
                    value={measuredNoiseDb}
                    onChange={(e) => setMeasuredNoiseDb(Number(e.target.value))}
                  />
                </div>

                <div className="flex items-center justify-between p-2.5 rounded border border-border/60">
                  <Label htmlFor="face-switch" className="text-xs">
                    Rostro visible en encuadre
                  </Label>
                  <Switch
                    id="face-switch"
                    checked={faceDetected}
                    onCheckedChange={setFaceDetected}
                  />
                </div>

                <div className="flex items-center justify-between p-2.5 rounded border border-border/60">
                  <Label htmlFor="ball-switch" className="text-xs">
                    Balón visible dentro del cuadro
                  </Label>
                  <Switch
                    id="ball-switch"
                    checked={ballDetected}
                    onCheckedChange={setBallDetected}
                  />
                </div>
              </div>
            </div>

            <Button
              type="button"
              onClick={handleSubmitEnvCheck}
              disabled={isBusy}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              <CheckCircle2 className="w-4 h-4 mr-2" />
              Validar Ambiente
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Paso 3: Prueba de Vida */}
      {step === "liveness" && (
        <Card className="border-border/70 shadow-sm">
          <CardHeader>
            <CardTitle className="text-lg font-semibold flex items-center gap-2">
              <Eye className="w-5 h-5 text-emerald-500" />
              Prueba de Vida
            </CardTitle>
            <CardDescription>
              Inclina la cabeza frente a la cámara.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Button
              type="button"
              onClick={handleSubmitLiveness}
              disabled={isBusy}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              <ShieldCheck className="w-4 h-4 mr-2" />
              Confirmar Prueba de Vida
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Paso 4: Calibración Audio-Video */}
      {step === "calibration" && (
        <Card className="border-border/70 shadow-sm">
          <CardHeader>
            <CardTitle className="text-lg font-semibold flex items-center gap-2">
              <Crosshair className="w-5 h-5 text-sky-500" />
              Calibración Audio-Video
            </CardTitle>
            <CardDescription>
              Da un toque claro al balón frente a la cámara.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Button
              type="button"
              onClick={handleConfirmCalibrationAndRecord}
              disabled={isBusy}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              <Play className="w-4 h-4 mr-2" />
              Registrar Toque e Iniciar Retos
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Paso 5: Grabación con Retos Dinámicos y Subida por Fragmentos a Garage S3 */}
      {step === "recording" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-7 space-y-4">
            <ChallengeHud
              activeCommand={currentPlannedCommand}
              remainingSeconds={segmentRemainingSec}
              approximateTouchCount={approxTouches}
              isSupervised={true}
              totalSegments={machine.segments.length || 4}
            />

            <Card className="border-border/70">
              <CardContent className="pt-4 space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-xs text-muted-foreground">
                    Fragmentos confirmados:{" "}
                    <span className="font-mono font-bold text-foreground">
                      {confirmedChunks.length > 0
                        ? confirmedChunks.join(", ")
                        : machine.confirmedChunks.join(", ") || "0"}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setApproxTouches((c) => c + 1)}
                    >
                      +1 Toque en Vivo
                    </Button>
                    <Button
                      type="button"
                      variant="destructive"
                      size="sm"
                      disabled={isBusy || isChunkUploading}
                      onClick={handleFinishRecordingAndScore}
                    >
                      <Square className="w-4 h-4 mr-1.5" />
                      Finalizar y Evaluar
                    </Button>
                  </div>
                </div>

                <div className="pt-3 border-t border-border/60">
                  <Label
                    htmlFor="direct-video-validation-input"
                    className="text-xs font-medium text-muted-foreground block mb-1.5"
                  >
                    O sube un video .mp4 / .webm
                  </Label>
                  <Input
                    id="direct-video-validation-input"
                    type="file"
                    accept=".mp4,.webm,video/mp4,video/webm"
                    onChange={handleUploadPreRecordedVideoForValidation}
                    disabled={isBusy}
                    className="text-xs cursor-pointer"
                  />
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="lg:col-span-5">
            <Card className="border-border/70">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold">
                  Vista en Vivo ({elapsedSeconds}s)
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="relative aspect-video rounded-lg overflow-hidden bg-neutral-950 border border-border flex items-center justify-center">
                  {stream ? (
                    <video
                      ref={videoRef}
                      autoPlay
                      muted
                      playsInline
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="text-center p-4 text-xs text-muted-foreground">
                      Sin cámara conectada.
                    </div>
                  )}
                  {isRecording && (
                    <Badge
                      variant="destructive"
                      className="absolute top-2 left-2 animate-pulse"
                    >
                      REC {elapsedSeconds}s
                    </Badge>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* Paso 6: Ensamblado en Garage S3 y Procesamiento IA */}
      {step === "processing" && (
        <Card className="border-border/70 text-center py-12">
          <CardContent className="space-y-3">
            <RefreshCw className="w-10 h-10 mx-auto text-emerald-500 animate-spin" />
            <CardTitle className="text-lg">Procesando video...</CardTitle>
          </CardContent>
        </Card>
      )}

      {/* Paso 7: Pantalla de Resultado Final */}
      {step === "result" && finalResult && (
        <div className="space-y-4">
          <FootballResultView
            result={finalResult}
            onRetrySession={handleResetAll}
          />
          {machine.assembledUri && (
            <div className="p-3 rounded-lg bg-secondary/40 border border-border/60 text-xs font-mono text-muted-foreground flex flex-wrap items-center justify-between gap-2">
              <span className="flex items-center gap-1.5">
                <CloudUpload className="w-4 h-4 text-emerald-500" />
                Garage S3 URI: {machine.assembledUri}
              </span>
              <span>SHA-256: {machine.assembledSha256?.slice(0, 24)}...</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

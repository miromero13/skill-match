import { useEffect, useRef, useState } from "react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  CheckCircle2,
  Play,
  RotateCcw,
  Volume2,
  Hand,
  Music,
  Sparkles,
  Sun,
  Award,
  AlertTriangle,
  XCircle,
} from "lucide-react"
import {
  FLUTE_NOTES_MAP,
  extractFluteAudioFeatures,
  type FluteNoteName,
} from "./flute-note-specs"

import { FluteHandOverlay } from "./flute-hand-overlay"
import { FLUTE_VISUAL_SCHEMA, freshHandFrame, type HandFrame } from "./flute-hand-features"
import { inferFlute, type FluteInference } from "@/services/dataset-sample-service"

interface FluteLiveValidatorProps {
  skillId?: string
  skillName?: string
}

interface ScoreNoteSegment {
  index: number
  targetNote: FluteNoteName
  targetHz: number
  durationSec: number
  handsRequired: 1 | 2
}

interface SegmentEvaluationResult {
  index: number
  targetNote: FluteNoteName
  targetHz: number
  handsRequired: 1 | 2
  detectedNote: FluteNoteName | "Silencio" | "Voz / Ruido (No Flauta)"
  avgMeasuredHz: number | null
  pitchScorePct: number
  leftHandDetected: boolean
  rightHandDetected: boolean
  handPostureOk: boolean | null
  handStatusLabel: string
  segmentTotalPct: number | null
}

export function FluteLiveValidator({
  skillName = "Flauta Dulce",
}: FluteLiveValidatorProps) {
  const handFrameRef = useRef<HandFrame | null>(null)
  const [sequenceStarted, setSequenceStarted] = useState(false)
  const [modelInfo, setModelInfo] = useState<FluteInference | null>(null)
  const segmentIndexRef = useRef(0)
  const generationRef = useRef(0)
  const predictionsRef = useRef<FluteInference[]>([])
  const [targetLevel, setTargetLevel] = useState<1 | 3>(1)
  const [step, setStep] = useState<"setup" | "playing" | "result">("setup")
  const [plan, setPlan] = useState<ScoreNoteSegment[]>([])
  const [activeIdx, setActiveIdx] = useState(0)
  const [segmentProgressPct, setSegmentProgressPct] = useState(0)
  const [cameraError, setCameraError] = useState<string | null>(null)

  // Live telemetry
  const [cameraReady, setCameraReady] = useState(false)
  const [leftHandLive, setLeftHandLive] = useState(false)
  const [rightHandLive, setRightHandLive] = useState(false)
  const [liveHz, setLiveHz] = useState<number | null>(null)
  const [liveDetectedNote, setLiveDetectedNote] =
    useState<FluteNoteName | null>(null)
  const [liveVoiceRejected, setLiveVoiceRejected] = useState(false)

  const [results, setResults] = useState<SegmentEvaluationResult[]>([])

  const videoRef = useRef<HTMLVideoElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const timerRef = useRef<number | null>(null)
  const telemetryIntervalRef = useRef<number | null>(null)

  // Per-segment accumulators
  const currentSegmentFluteHzRef = useRef<number[]>([])
  const currentSegmentVoiceRejectionsRef = useRef<number>(0)
  const currentSegmentTotalFramesRef = useRef<number>(0)
  const currentSegmentLeftHandOkFramesRef = useRef<number>(0)
  const currentSegmentRightHandOkFramesRef = useRef<number>(0)

  const buildChallengePlan = (level: 1 | 3): ScoreNoteSegment[] => {
    const level1Pool: FluteNoteName[] = ["SI", "LA", "SOL", "DO6", "RE6"]
    const level3Pool: FluteNoteName[] = [
      "SOL",
      "FA#",
      "MI",
      "RE",
      "DO",
      "RE6",
      "MI6",
    ]
    const sequence = level === 1 ? level1Pool : level3Pool
    const durationSec = level === 1 ? 4 : 3

    return sequence.map((note, idx) => ({
      index: idx,
      targetNote: note,
      targetHz: Math.round(FLUTE_NOTES_MAP[note].hz),
      durationSec,
      handsRequired: FLUTE_NOTES_MAP[note].handsRequired,
    }))
  }

  useEffect(() => {
    setPlan(buildChallengePlan(targetLevel))
  }, [targetLevel])

  // Attach MediaStream to <video> whenever `step === "playing"` mounts the video element
  useEffect(() => {
    if (step === "playing" && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current
      void videoRef.current.play().catch(() => undefined)
    }
  }, [step])

  const cleanupMedia = () => {
    generationRef.current += 1
    handFrameRef.current = null
    setSequenceStarted(false)
    if (timerRef.current) {
      window.clearInterval(timerRef.current)
      timerRef.current = null
    }
    if (telemetryIntervalRef.current) {
      window.clearInterval(telemetryIntervalRef.current)
      telemetryIntervalRef.current = null
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
    if (audioCtxRef.current) {
      void audioCtxRef.current.close().catch(() => undefined)
      audioCtxRef.current = null
    }
    setCameraReady(false)
    setLeftHandLive(false)
    setRightHandLive(false)
  }

  useEffect(() => {
    return () => {
      cleanupMedia()
    }
  }, [])

  const startLiveValidation = async () => {
    setCameraError(null)
    setModelInfo(null)
    cleanupMedia()
    const generation = generationRef.current
    segmentIndexRef.current = 0
    predictionsRef.current = []

    const generatedPlan = buildChallengePlan(targetLevel)
    setPlan(generatedPlan)
    setResults([])
    setActiveIdx(0)
    setSegmentProgressPct(0)

    let media: MediaStream
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error("Tu navegador no permite acceso a cámara y micrófono.")
      }
      media = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" },
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        },
      })
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : "No se pudo encender la cámara o el micrófono."
      setCameraError(
        `No se pudo encender la cámara o el micrófono (${msg}). Revisa los permisos del navegador.`
      )
      return
    }

    streamRef.current = media
    setStep("playing")

    // Start Web Audio + Video Hand Zone analysis loop
    let analyser: AnalyserNode | null = null
    let sampleRate = 44100
    if (typeof window !== "undefined" && "AudioContext" in window) {
      const ctx = new window.AudioContext()
      audioCtxRef.current = ctx
      sampleRate = ctx.sampleRate
      const source = ctx.createMediaStreamSource(media)
      analyser = ctx.createAnalyser()
      analyser.fftSize = 2048
      source.connect(analyser)
    }

    let pending = false
    let started = false
    telemetryIntervalRef.current = window.setInterval(async () => {
      if (!streamRef.current || !streamRef.current.active) {
        return
      }

      if (pending || !analyser) return
      const index = segmentIndexRef.current
      const segment = generatedPlan[index]
      const frame = freshHandFrame(handFrameRef.current)
      if (!frame || !segment) return
      const visualFeatures = frame.features
      setCameraReady(true)
      setLeftHandLive(visualFeatures[0] === 1)
      setRightHandLive(visualFeatures[64] === 1)
      if (!started && visualFeatures[0] + visualFeatures[64] < segment.handsRequired) return
      const audioFeatures = extractFluteAudioFeatures(analyser, sampleRate)
      pending = true
      try {
        const response = await inferFlute({ target_note: segment.targetNote, audio_features: audioFeatures, visual_features: visualFeatures, visual_schema: FLUTE_VISUAL_SCHEMA })
        if (generation !== generationRef.current || index !== segmentIndexRef.current) return
        if (!response.data) throw new Error(response.message)
        const prediction = response.data
        if (!started) {
          started = true
          setSequenceStarted(true)
          runPartituraSequence(generatedPlan)
        }
        predictionsRef.current.push(prediction)
        setModelInfo(prediction)
        setLiveHz(audioFeatures[24] * 1500 || null)
        const note = prediction.sound_class
        setLiveDetectedNote(Object.hasOwn(FLUTE_NOTES_MAP, note) ? note as FluteNoteName : null)
        setLiveVoiceRejected(note === "NO_FLAUTA")
        if (note === "NO_FLAUTA") currentSegmentVoiceRejectionsRef.current += 1
        else currentSegmentFluteHzRef.current.push(audioFeatures[24] * 1500)
      } catch (err: unknown) {
        if (generation !== generationRef.current) return
        cleanupMedia()
        setCameraError(err instanceof Error ? err.message : "No se pudo ejecutar la inferencia.")
        setStep("setup")
        return
      } finally { pending = false }

      currentSegmentTotalFramesRef.current += 1
      if (visualFeatures[0] === 1) currentSegmentLeftHandOkFramesRef.current += 1
      if (visualFeatures[64] === 1) currentSegmentRightHandOkFramesRef.current += 1
    }, 300)
  }

  const runPartituraSequence = (segments: ScoreNoteSegment[]) => {
    let segIdx = 0
    let elapsedMs = 0
    currentSegmentFluteHzRef.current = []
    currentSegmentVoiceRejectionsRef.current = 0
    currentSegmentTotalFramesRef.current = 0
    currentSegmentLeftHandOkFramesRef.current = 0
    currentSegmentRightHandOkFramesRef.current = 0

    const collectedResults: SegmentEvaluationResult[] = []

    if (timerRef.current) window.clearInterval(timerRef.current)

    timerRef.current = window.setInterval(() => {
      const currentSeg = segments[segIdx]
      if (!currentSeg) return

      const segDurationMs = currentSeg.durationSec * 1000
      elapsedMs += 150
      const pct = Math.min(100, Math.round((elapsedMs / segDurationMs) * 100))
      setSegmentProgressPct(pct)

      if (elapsedMs >= segDurationMs) {
        const fluteHzReadings = currentSegmentFluteHzRef.current
        const totalFrames = Math.max(1, currentSegmentTotalFramesRef.current)
        const leftRatio = currentSegmentLeftHandOkFramesRef.current / totalFrames
        const rightRatio = currentSegmentRightHandOkFramesRef.current / totalFrames

        // Require hand presence in at least 35% of frames during the note
        const leftDetected =
          currentSegmentTotalFramesRef.current > 0 && leftRatio >= 0.35
        const rightDetected =
          currentSegmentTotalFramesRef.current > 0 && rightRatio >= 0.35

        const predictions = predictionsRef.current
        if (predictions.length === 0) {
          cleanupMedia()
          setCameraError("Sin inferencias del modelo para este segmento. Repite la prueba.")
          setStep("setup")
          return
        }
        const evaluable = predictions.filter(p => p.posture_evaluable)
        const handPostureOk = evaluable.length < 3 || evaluable.length / predictions.length < 0.7
          ? null : evaluable.filter(p => p.posture_ok).length / evaluable.length >= 0.5

        const avgHz = fluteHzReadings.length > 0
          ? Math.round(fluteHzReadings.reduce((a, b) => a + b, 0) / fluteHzReadings.length) : null
        const pitchScore = Math.round(100 * predictions.filter(p => p.sound_ok).length / predictions.length)
        const votes = new Map<string, number>()
        predictions.forEach(p => votes.set(p.sound_class, (votes.get(p.sound_class) ?? 0) + 1))
        const winner = [...votes].sort((a, b) => b[1] - a[1])[0][0]
        const detected = Object.hasOwn(FLUTE_NOTES_MAP, winner) ? winner as FluteNoteName : "Voz / Ruido (No Flauta)"
        const handStatusLabel = handPostureOk === null
          ? predictions.find(p => p.posture_reason)?.posture_reason ?? "Digitación inconclusa: faltan observaciones fiables."
          : handPostureOk ? "Coincide con la digitación aprendida" : "No coincide con la digitación aprendida"

        // Combined segment score:
        // If no valid flute note matched (pitchScore === 0), the note fails (0%).
        // If the note matched, 75% comes from pitch accuracy and 25% from verified hand posture in camera.
        const segmentTotalPct = handPostureOk === null ? null :
          pitchScore === 0
            ? 0
            : Math.round(pitchScore * 0.75 + (handPostureOk ? 25 : 0))

        collectedResults.push({
          index: currentSeg.index,
          targetNote: currentSeg.targetNote,
          targetHz: currentSeg.targetHz,
          handsRequired: currentSeg.handsRequired,
          detectedNote: detected,
          avgMeasuredHz: avgHz,
          pitchScorePct: pitchScore,
          leftHandDetected: leftDetected,
          rightHandDetected: rightDetected,
          handPostureOk,
          handStatusLabel,
          segmentTotalPct,
        })

        segIdx += 1
        segmentIndexRef.current = segIdx
        predictionsRef.current = []
        elapsedMs = 0
        currentSegmentFluteHzRef.current = []
        currentSegmentVoiceRejectionsRef.current = 0
        currentSegmentTotalFramesRef.current = 0
        currentSegmentLeftHandOkFramesRef.current = 0
        currentSegmentRightHandOkFramesRef.current = 0

        if (segIdx < segments.length) {
          setActiveIdx(segIdx)
          setSegmentProgressPct(0)
        } else {
          cleanupMedia()
          setResults(collectedResults)
          setStep("result")
        }
      }
    }, 150)
  }

  const activeSegment = plan[activeIdx] || plan[0]
  const activeNoteSpec = activeSegment
    ? FLUTE_NOTES_MAP[activeSegment.targetNote]
    : FLUTE_NOTES_MAP.SI

  const overallScore = results.some(r => r.segmentTotalPct === null) ? null :
    results.length > 0
      ? Math.round(
          results.reduce((acc, r) => acc + (r.segmentTotalPct ?? 0), 0) / results.length
        )
      : 0

  const isApproved = overallScore !== null && overallScore >= 75

  return (
    <div className="space-y-6">
      {step === "playing" && !sequenceStarted && <Alert><AlertDescription>Calibra la flauta y muestra tus manos. La secuencia comenzará al recibir la primera inferencia. Los puntos muestran estimaciones de articulaciones, no confirman agujeros tapados.</AlertDescription></Alert>}
      {modelInfo && <Alert variant={modelInfo.validated ? "default" : "destructive"}>
        <AlertDescription>Modelo {modelInfo.model_version} · {modelInfo.validated ? "Validado con participantes independientes" : "No verificado con participantes independientes; resultado experimental"}</AlertDescription>
      </Alert>}

      {cameraError && (
        <Alert variant="destructive">
          <AlertTriangle className="w-4 h-4" />
          <AlertTitle>Error de Cámara o Micrófono</AlertTitle>
          <AlertDescription>{cameraError}</AlertDescription>
        </Alert>
      )}

      <Card className="border-border/60 shadow-sm">
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <Badge className="bg-emerald-600 text-white text-xs">
                  <Sparkles className="w-3.5 h-3.5 mr-1" />
                  Validador Estricto en Vivo (Timbre de Flauta + Manos en Cámara)
                </Badge>
                <Badge variant="outline" className="text-xs">
                  {skillName}
                </Badge>
              </div>
              <CardTitle className="text-lg font-bold mt-1.5">
                Prueba Interactiva de Flauta (Sonido + Posición de Manos)
              </CardTitle>
              <CardDescription className="text-xs">
                Compara sonido y articulaciones con tus ejemplos etiquetados.
                Calibra el eje de la flauta y observa los dedos sobre el video.
                Sin evidencia visual suficiente, el resultado será inconcluso.
              </CardDescription>
            </div>

            {step === "setup" && (
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant={targetLevel === 1 ? "default" : "outline"}
                  onClick={() => setTargetLevel(1)}
                  className={
                    targetLevel === 1
                      ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                      : ""
                  }
                >
                  Probar Examen Nivel 1 (Principiante)
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant={targetLevel === 3 ? "default" : "outline"}
                  onClick={() => setTargetLevel(3)}
                  className={
                    targetLevel === 3
                      ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                      : ""
                  }
                >
                  Probar Examen Nivel 3 (Avanzado)
                </Button>
              </div>
            )}
          </div>
        </CardHeader>

        <CardContent className="space-y-5">
          {step === "setup" && (
            <div className="space-y-4">
              <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/5 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-sm font-bold text-foreground flex items-center gap-2">
                    <Music className="w-4 h-4 text-emerald-500" />
                    {targetLevel === 1
                      ? "Partitura Dinámica — Nivel 1 (Principiante: 1 Mano Arriba, Ritmo Pausado)"
                      : "Partitura Dinámica — Nivel 3 (Avanzado: Ambas Manos + FA# y Agudos)"}
                  </span>
                  <Badge variant="secondary" className="text-xs">
                    {plan.length} notas •{" "}
                    {plan.reduce((a, b) => a + b.durationSec, 0)} segundos totales
                  </Badge>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {plan.map((seg, idx) => (
                    <div
                      key={seg.index}
                      className="flex items-center gap-1.5 px-3 py-2 rounded-lg border bg-card text-xs"
                    >
                      <span className="font-mono text-muted-foreground">
                        #{idx + 1}
                      </span>
                      <span className="font-bold text-sm text-emerald-600 dark:text-emerald-400">
                        {FLUTE_NOTES_MAP[seg.targetNote].displayName}
                      </span>
                      <span className="text-[10px] text-muted-foreground font-mono">
                        ({seg.targetHz}Hz • {seg.durationSec}s • {seg.handsRequired}M)
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <Button
                type="button"
                className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-semibold py-2.5"
                onClick={() => void startLiveValidation()}
              >
                <Play className="w-4 h-4 mr-2 fill-current" />
                Iniciar Prueba en Vivo de Nivel {targetLevel} (Encender Cámara y Micrófono)
              </Button>
            </div>
          )}

          {step === "playing" && activeSegment && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-center">
              {/* Partitura Activa e Instrucción de Dedos */}
              <div className="lg:col-span-5 p-4 rounded-xl border-2 border-emerald-500 bg-card space-y-4">
                <div className="flex items-center justify-between">
                  <Badge className="bg-emerald-600 text-white text-xs">
                    Nota {activeIdx + 1} de {plan.length}
                  </Badge>
                  <Badge variant="outline" className="text-xs font-mono">
                    <Hand className="w-3.5 h-3.5 mr-1" />
                    {activeNoteSpec.handsRequired === 2
                      ? "Exige 2 Manos en Cámara"
                      : "Exige Mano Izquierda Arriba"}
                  </Badge>
                </div>

                <div className="text-center py-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 space-y-1">
                  <span className="text-xs uppercase tracking-wider text-muted-foreground block">
                    Toca ahora con la flauta:
                  </span>
                  <div className="text-4xl sm:text-5xl font-extrabold text-emerald-600 dark:text-emerald-400">
                    {activeNoteSpec.displayName}
                  </div>
                  <span className="text-xs font-mono text-muted-foreground block">
                    Frecuencia objetivo: {activeSegment.targetHz} Hz
                  </span>
                </div>

                <p className="text-xs font-medium text-foreground text-center">
                  {activeNoteSpec.handTip}
                </p>

                {/* Diagrama de los 7 huecos */}
                <div className="flex items-center justify-center gap-1.5 py-2">
                  {activeNoteSpec.frontHoles.map((covered, i) => (
                    <div
                      key={i}
                      className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold border ${
                        covered
                          ? i < 3
                            ? "bg-emerald-600 text-white border-emerald-500"
                            : "bg-sky-600 text-white border-sky-500"
                          : "bg-background text-muted-foreground border-border"
                      }`}
                    >
                      {i + 1}
                    </div>
                  ))}
                </div>

                <div className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground">
                      Tiempo de esta nota:
                    </span>
                    <span className="font-mono font-semibold">
                      {segmentProgressPct}%
                    </span>
                  </div>
                  <Progress value={segmentProgressPct} className="h-2.5" />
                </div>
              </div>

              {/* Cámara en Vivo con Detección Real de Zonas de Manos y Filtro Antivoz */}
              <div className="lg:col-span-7 space-y-3">
                <div className="relative aspect-video rounded-xl overflow-hidden bg-neutral-950 border border-border">
                  <video
                    ref={(el) => {
                      videoRef.current = el
                      if (el && streamRef.current && el.srcObject !== streamRef.current) {
                        el.srcObject = streamRef.current
                        void el.play().catch(() => undefined)
                      }
                    }}
                    autoPlay
                    muted
                    playsInline
                    className="w-full h-full object-contain"
                  />

                  <FluteHandOverlay videoRef={videoRef}
                    onFrame={frame => { handFrameRef.current = frame }} />
                  <div className="absolute inset-0 p-3 flex flex-col justify-between pointer-events-none">
                    {/* Top Telemetry Bar */}
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <Badge className="bg-black/80 text-white text-xs font-mono">
                        <Sun className="w-3.5 h-3.5 mr-1 text-amber-400" />
                        {cameraReady
                          ? "Cámara activa · articulaciones"
                          : "Iniciando cámara..."}
                      </Badge>

                      <Badge
                        className={
                          liveVoiceRejected
                            ? "bg-red-600 text-white text-xs font-mono"
                            : liveHz
                            ? liveDetectedNote === activeSegment.targetNote
                              ? "bg-emerald-600 text-white text-xs font-mono"
                              : "bg-amber-600 text-white text-xs font-mono"
                            : "bg-black/80 text-neutral-300 text-xs font-mono"
                        }
                      >
                        <Volume2 className="w-3.5 h-3.5 mr-1" />
                        {liveVoiceRejected
                          ? "⚠️ Voz / Ruido rechazado (Usa la flauta)"
                          : liveHz
                          ? `Flauta: ${liveDetectedNote} (${liveHz} Hz)`
                          : "Esperando sonido de flauta..."}
                      </Badge>
                    </div>

                    {/* Recuadros Reales de Detección de Mano Izquierda (Arriba) y Derecha (Abajo) */}
                    <div className="ml-auto mt-2 mb-auto w-36 flex flex-col gap-2">
                      <div
                        className={`rounded-lg px-3 py-2 text-center border-2 transition-colors text-xs font-bold ${
                          leftHandLive
                            ? "border-emerald-400 bg-emerald-950/65 text-emerald-200"
                            : "border-red-500/80 border-dashed bg-black/60 text-red-300"
                        }`}
                      >
                        {leftHandLive
                          ? "Articulaciones A detectadas"
                          : "Mano A no detectada"}
                      </div>

                      <div
                        className={`rounded-lg px-3 py-2 text-center border-2 transition-colors text-xs font-bold ${
                          rightHandLive
                            ? "border-sky-400 bg-sky-950/65 text-sky-200"
                            : activeNoteSpec.handsRequired === 2
                            ? "border-red-500/80 border-dashed bg-black/60 text-red-300"
                            : "border-neutral-500/60 border-dashed bg-black/45 text-neutral-300"
                        }`}
                      >
                        {rightHandLive
                          ? "Articulaciones B detectadas"
                          : activeNoteSpec.handsRequired === 2
                          ? "Mano B no detectada"
                          : "Mano B opcional"}
                      </div>
                    </div>

                    {/* Barra inferior de progreso de toda la partitura */}
                    <div className="flex items-center gap-1.5 bg-black/80 p-2 rounded-lg">
                      {plan.map((seg, idx) => (
                        <div
                          key={seg.index}
                          className={`flex-1 text-center py-1 rounded text-xs font-bold ${
                            idx === activeIdx
                              ? "bg-emerald-600 text-white"
                              : idx < activeIdx
                              ? "bg-emerald-900/70 text-emerald-300"
                              : "bg-neutral-800 text-neutral-400"
                          }`}
                        >
                          {FLUTE_NOTES_MAP[seg.targetNote].displayName}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {step === "result" && (
            <div className="space-y-4">
              <div className="p-4 rounded-xl border border-border bg-card flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <Award
                    className={`w-10 h-10 ${
                      isApproved ? "text-emerald-500" : "text-amber-500"
                    }`}
                  />
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-lg font-bold">
                        Resultado de Validación — Nivel {targetLevel}
                      </h3>
                      <Badge
                        className={
                          overallScore === null ? "bg-amber-600 text-white" : isApproved
                            ? "bg-emerald-600 text-white"
                            : "bg-destructive text-white"
                        }
                      >
                        {overallScore === null ? "INCONCLUSO · NO SE PUNTÚA" : isApproved ? "APROBADO" : "REQUIERE REVISIÓN"}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Coincidencia de sonido aprendido (75%) y digitación aprendida (25%).
                      La frecuencia es una estimación independiente, no la etiqueta del modelo.
                    </p>
                  </div>
                </div>

                <div className="text-right">
                  <span className="text-xs text-muted-foreground block">
                    Puntaje Global
                  </span>
                  <span
                    className={`text-3xl font-extrabold ${
                      isApproved ? "text-emerald-600" : "text-destructive"
                    }`}
                  >
                    {overallScore === null ? "Sin puntuación" : `${overallScore} / 100`}
                  </span>
                </div>
              </div>

              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">#</TableHead>
                    <TableHead className="text-xs">Nota Pedida</TableHead>
                    <TableHead className="text-xs">Nota predicha / Hz estimados</TableHead>
                    <TableHead className="text-xs">Manos en Cámara</TableHead>
                    <TableHead className="text-xs text-right">
                      Inferencias coincidentes
                    </TableHead>
                    <TableHead className="text-xs text-right">
                      Total Segmento
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {results.map((r, i) => (
                    <TableRow key={r.index}>
                      <TableCell className="text-xs font-mono">
                        #{i + 1}
                      </TableCell>
                      <TableCell className="text-xs font-bold">
                        {FLUTE_NOTES_MAP[r.targetNote].displayName} ({r.targetHz} Hz)
                      </TableCell>
                      <TableCell className="text-xs font-mono">
                        {r.detectedNote === r.targetNote ? (
                          <span className="text-emerald-600 dark:text-emerald-400 font-bold">
                            ✓ {r.detectedNote} ({r.avgMeasuredHz} Hz)
                          </span>
                        ) : (
                          <span className="text-destructive font-semibold">
                            ✗ {r.detectedNote}{" "}
                            {r.avgMeasuredHz ? `(${r.avgMeasuredHz} Hz)` : ""}
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="text-xs">
                        {r.handPostureOk === null ? <Badge variant="outline" className="text-[10px] whitespace-normal border-amber-500 text-amber-700">{r.handStatusLabel}</Badge> : r.handPostureOk ? (
                          <Badge
                            variant="outline"
                            className="border-emerald-500/40 text-emerald-600 text-[10px]"
                          >
                            <CheckCircle2 className="w-3 h-3 mr-1" />{" "}
                            {r.handStatusLabel}
                          </Badge>
                        ) : (
                          <Badge
                            variant="destructive"
                            className="text-[10px]"
                          >
                            <XCircle className="w-3 h-3 mr-1" />{" "}
                            {r.handStatusLabel}
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-xs font-mono text-right">
                        {r.pitchScorePct}%
                      </TableCell>
                      <TableCell className="text-xs font-bold text-right">
                        {r.segmentTotalPct === null ? "Inconcluso" : `${r.segmentTotalPct}%`}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              <div className="flex justify-end">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setStep("setup")}
                >
                  <RotateCcw className="w-4 h-4 mr-1.5" />
                  Realizar Otra Prueba en Vivo
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

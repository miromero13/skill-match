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
  Square,
  RotateCcw,
  Volume2,
  Hand,
  Music,
  Sparkles,
  Sun,
  Award,
  AlertTriangle,
  XCircle,
  Radio,
} from "lucide-react"
import {
  FLUTE_NOTES_MAP,
  extractFluteAudioFeatures,
  type FluteNoteName,
} from "./flute-note-specs"

import { FluteHandOverlay } from "./flute-hand-overlay"
import {
  FLUTE_VISUAL_DIM,
  FLUTE_VISUAL_SCHEMA,
  LEFT_HAND_PRESENCE_IDX,
  RIGHT_HAND_PRESENCE_IDX,
  countDetectedHands,
  freshHandFrame,
  type HandFrame,
} from "./flute-hand-features"
import { inferFlute, type FluteInference } from "@/services/dataset-sample-service"

interface FluteLiveValidatorProps {
  skillId?: string
  skillName?: string
}

interface ScoreNoteSegment {
  index: number
  targetNote: FluteNoteName
  durationSec: number
  handsRequired: 1 | 2
}

interface SegmentEvaluationResult {
  index: number
  targetNote: FluteNoteName
  handsRequired: 1 | 2
  detectedNote: FluteNoteName | "Voz / Ruido (No Flauta)"
  soundScorePct: number
  leftHandDetected: boolean
  rightHandDetected: boolean
  handPostureOk: boolean | null
  handStatusLabel: string
  segmentTotalPct: number | null
}

type ValidatorMode = "free" | "exam"

export function FluteLiveValidator({
  skillName = "Flauta Dulce",
}: FluteLiveValidatorProps) {
  const handFrameRef = useRef<HandFrame | null>(null)
  const [mode, setMode] = useState<ValidatorMode>("free")
  const [sequenceStarted, setSequenceStarted] = useState(false)
  const [modelInfo, setModelInfo] = useState<FluteInference | null>(null)
  const [recentConfirmedNotes, setRecentConfirmedNotes] = useState<FluteNoteName[]>([])
  const segmentIndexRef = useRef(0)
  const generationRef = useRef(0)
  const predictionsRef = useRef<FluteInference[]>([])
  const postureWindowRef = useRef<Array<Array<{ label: string; probability: number }>>>([])
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
  const [liveDetectedNote, setLiveDetectedNote] =
    useState<FluteNoteName | null>(null)
  const [liveVoiceRejected, setLiveVoiceRejected] = useState(false)

  const [results, setResults] = useState<SegmentEvaluationResult[]>([])

  const videoRef = useRef<HTMLVideoElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const timerRef = useRef<number | null>(null)
  const telemetryIntervalRef = useRef<number | null>(null)

  // Per-segment accumulators (exam mode)
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

  const openCameraAndAudio = async (): Promise<{
    media: MediaStream
    analyser: AnalyserNode | null
    sampleRate: number
  } | null> => {
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
      return null
    }

    streamRef.current = media
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
    return { media, analyser, sampleRate }
  }

  const startFreeDetection = async () => {
    setCameraError(null)
    setModelInfo(null)
    setRecentConfirmedNotes([])
    postureWindowRef.current = []
    cleanupMedia()
    const generation = generationRef.current

    const devices = await openCameraAndAudio()
    if (!devices) return
    const { analyser, sampleRate } = devices

    setStep("playing")
    setSequenceStarted(true)

    let pending = false
    telemetryIntervalRef.current = window.setInterval(async () => {
      if (!streamRef.current || !streamRef.current.active) return
      if (pending || !analyser) return
      const frame = freshHandFrame(handFrameRef.current)
      const visualFeatures = frame?.features ?? Array<number>(FLUTE_VISUAL_DIM).fill(0)
      setCameraReady(true)
      setLeftHandLive(visualFeatures[LEFT_HAND_PRESENCE_IDX] === 1)
      setRightHandLive(visualFeatures[RIGHT_HAND_PRESENCE_IDX] === 1)

      const audioFeatures = extractFluteAudioFeatures(analyser, sampleRate)
      pending = true
      try {
        const response = await inferFlute({
          target_note: null,
          audio_features: audioFeatures,
          visual_features: visualFeatures,
          visual_schema: FLUTE_VISUAL_SCHEMA,
        })
        if (generation !== generationRef.current) return
        if (!response.data) throw new Error(response.message)
        const rawPrediction = response.data

        // 3-frame temporal smoothing for posture probabilities
        let prediction = rawPrediction
        if (rawPrediction.posture_evaluable && rawPrediction.top_posture_classes) {
          postureWindowRef.current = [
            ...postureWindowRef.current.slice(-2),
            rawPrediction.top_posture_classes,
          ]
          const avgScores = new Map<string, number>()
          const winLen = postureWindowRef.current.length
          for (const entries of postureWindowRef.current) {
            for (const entry of entries) {
              avgScores.set(entry.label, (avgScores.get(entry.label) ?? 0) + entry.probability / winLen)
            }
          }
          const smoothedTop = [...avgScores.entries()]
            .map(([label, probability]) => ({ label, probability: Number(probability.toFixed(4)) }))
            .sort((a, b) => b.probability - a.probability)
            .slice(0, 3)

          if (smoothedTop.length > 0) {
            const topPosture = smoothedTop[0]
            const soundNote = rawPrediction.sound_class
            const isWrong = topPosture.label === "INCORRECTA" && topPosture.probability >= 0.5
            const soundInTop3 = smoothedTop.some(
              (item) => item.label === soundNote && item.probability >= 0.15
            )
            const smoothedCombinedMatch = Boolean(
              rawPrediction.sound_ok && !isWrong && soundInTop3
            )
            prediction = {
              ...rawPrediction,
              posture_class: topPosture.label,
              posture_confidence: topPosture.probability,
              top_posture_classes: smoothedTop,
              combined_match: smoothedCombinedMatch,
              combined_note: smoothedCombinedMatch ? soundNote : null,
            }
          }
        } else {
          postureWindowRef.current = []
        }

        setModelInfo(prediction)
        const soundNote = prediction.sound_class
        setLiveDetectedNote(
          Object.hasOwn(FLUTE_NOTES_MAP, soundNote)
            ? (soundNote as FluteNoteName)
            : null
        )
        setLiveVoiceRejected(soundNote === "NO_FLAUTA")
        if (
          prediction.combined_match &&
          prediction.combined_note &&
          Object.hasOwn(FLUTE_NOTES_MAP, prediction.combined_note)
        ) {
          const confirmed = prediction.combined_note as FluteNoteName
          setRecentConfirmedNotes((prev) =>
            prev[0] === confirmed ? prev : [confirmed, ...prev].slice(0, 8)
          )
        }
      } catch (err: unknown) {
        if (generation !== generationRef.current) return
        cleanupMedia()
        setCameraError(
          err instanceof Error ? err.message : "No se pudo ejecutar la inferencia."
        )
        setStep("setup")
      } finally {
        pending = false
      }
    }, 280)
  }

  const startExamValidation = async () => {
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

    const devices = await openCameraAndAudio()
    if (!devices) return
    const { analyser, sampleRate } = devices

    setStep("playing")

    let pending = false
    let started = false
    telemetryIntervalRef.current = window.setInterval(async () => {
      if (!streamRef.current || !streamRef.current.active) return
      if (pending || !analyser) return
      const index = segmentIndexRef.current
      const segment = generatedPlan[index]
      const frame = freshHandFrame(handFrameRef.current)
      if (!frame || !segment) return
      const visualFeatures = frame.features
      setCameraReady(true)
      setLeftHandLive(visualFeatures[LEFT_HAND_PRESENCE_IDX] === 1)
      setRightHandLive(visualFeatures[RIGHT_HAND_PRESENCE_IDX] === 1)
      if (!started && countDetectedHands(visualFeatures) < segment.handsRequired) return
      const audioFeatures = extractFluteAudioFeatures(analyser, sampleRate)
      pending = true
      try {
        const response = await inferFlute({
          target_note: segment.targetNote,
          audio_features: audioFeatures,
          visual_features: visualFeatures,
          visual_schema: FLUTE_VISUAL_SCHEMA,
        })
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
        const note = prediction.sound_class
        setLiveDetectedNote(
          Object.hasOwn(FLUTE_NOTES_MAP, note) ? (note as FluteNoteName) : null
        )
        setLiveVoiceRejected(note === "NO_FLAUTA")
      } catch (err: unknown) {
        if (generation !== generationRef.current) return
        cleanupMedia()
        setCameraError(
          err instanceof Error ? err.message : "No se pudo ejecutar la inferencia."
        )
        setStep("setup")
        return
      } finally {
        pending = false
      }

      currentSegmentTotalFramesRef.current += 1
      if (visualFeatures[LEFT_HAND_PRESENCE_IDX] === 1) {
        currentSegmentLeftHandOkFramesRef.current += 1
      }
      if (visualFeatures[RIGHT_HAND_PRESENCE_IDX] === 1) {
        currentSegmentRightHandOkFramesRef.current += 1
      }
    }, 300)
  }

  const runPartituraSequence = (segments: ScoreNoteSegment[]) => {
    let segIdx = 0
    let elapsedMs = 0
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
        const totalFrames = Math.max(1, currentSegmentTotalFramesRef.current)
        const leftRatio = currentSegmentLeftHandOkFramesRef.current / totalFrames
        const rightRatio = currentSegmentRightHandOkFramesRef.current / totalFrames

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
        const evaluable = predictions.filter((p) => p.posture_evaluable)
        const handPostureOk =
          evaluable.length < 3 || evaluable.length / predictions.length < 0.7
            ? null
            : evaluable.filter((p) => p.posture_ok).length / evaluable.length >= 0.5

        const soundScore = Math.round(
          (100 * predictions.filter((p) => p.sound_ok).length) / predictions.length
        )
        const votes = new Map<string, number>()
        predictions.forEach((p) =>
          votes.set(p.sound_class, (votes.get(p.sound_class) ?? 0) + 1)
        )
        const winner = [...votes].sort((a, b) => b[1] - a[1])[0][0]
        const detected: FluteNoteName | "Voz / Ruido (No Flauta)" = Object.hasOwn(
          FLUTE_NOTES_MAP,
          winner
        )
          ? (winner as FluteNoteName)
          : "Voz / Ruido (No Flauta)"
        const handStatusLabel =
          handPostureOk === null
            ? predictions.find((p) => p.posture_reason)?.posture_reason ??
              "Digitación inconclusa: faltan observaciones fiables."
            : handPostureOk
            ? "Coincide con la digitación aprendida"
            : "No coincide con la digitación aprendida"

        const segmentTotalPct =
          handPostureOk === null
            ? null
            : soundScore === 0
            ? 0
            : Math.round(soundScore * 0.75 + (handPostureOk ? 25 : 0))

        collectedResults.push({
          index: currentSeg.index,
          targetNote: currentSeg.targetNote,
          handsRequired: currentSeg.handsRequired,
          detectedNote: detected,
          soundScorePct: soundScore,
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

  const stopLiveSession = () => {
    cleanupMedia()
    setStep("setup")
  }

  const activeSegment = plan[activeIdx] || plan[0]
  const activeNoteSpec = activeSegment
    ? FLUTE_NOTES_MAP[activeSegment.targetNote]
    : FLUTE_NOTES_MAP.SI

  const overallScore = results.some((r) => r.segmentTotalPct === null)
    ? null
    : results.length > 0
    ? Math.round(
        results.reduce((acc, r) => acc + (r.segmentTotalPct ?? 0), 0) /
          results.length
      )
    : 0

  const isApproved = overallScore !== null && overallScore >= 75

  const formatNoteLabel = (label: string) =>
    Object.hasOwn(FLUTE_NOTES_MAP, label)
      ? FLUTE_NOTES_MAP[label as FluteNoteName].displayName
      : label

  return (
    <div className="space-y-6">
      {step === "playing" && mode === "exam" && !sequenceStarted && (
        <Alert>
          <AlertDescription>
            Muestra tus manos frente a la cámara. La secuencia comenzará automáticamente al recibir la primera inferencia.
          </AlertDescription>
        </Alert>
      )}
      {modelInfo && (
        <Alert variant={modelInfo.validated ? "default" : "default"}>
          <AlertDescription>
            Modelo {modelInfo.model_version} ·{" "}
            {modelInfo.validated
              ? "Validado con participantes independientes"
              : "Modo experimental (entrenado con 1 participante)"}
          </AlertDescription>
        </Alert>
      )}

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
                  Validador Dual en Vivo (Sonido de Flauta + Posición de Manos)
                </Badge>
                <Badge variant="outline" className="text-xs">
                  {skillName}
                </Badge>
              </div>
              <CardTitle className="text-lg font-bold mt-1.5">
                Detección de Notas por Timbre de Flauta y Digitación en Cámara
              </CardTitle>
              <CardDescription className="text-xs">
                Reconoce las notas aprendidas por el sonido real de la flauta (sin medir frecuencia en Hz) y las articulaciones de tus manos.
              </CardDescription>
            </div>

            {step === "setup" && (
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant={mode === "free" ? "default" : "outline"}
                  onClick={() => setMode("free")}
                  className={
                    mode === "free"
                      ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                      : ""
                  }
                >
                  <Radio className="w-3.5 h-3.5 mr-1.5" />
                  Detección Libre
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant={mode === "exam" ? "default" : "outline"}
                  onClick={() => setMode("exam")}
                  className={
                    mode === "exam"
                      ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                      : ""
                  }
                >
                  <Music className="w-3.5 h-3.5 mr-1.5" />
                  Examen Partitura
                </Button>
              </div>
            )}
          </div>
        </CardHeader>

        <CardContent className="space-y-5">
          {step === "setup" && mode === "free" && (
            <div className="space-y-4">
              <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/5 space-y-2">
                <span className="text-sm font-bold text-foreground flex items-center gap-2">
                  <Radio className="w-4 h-4 text-emerald-500" />
                  Modo Detección Libre en Tiempo Real
                </span>
                <p className="text-xs text-muted-foreground">
                  Ponte frente a la cámara y toca cualquier nota entrenada en tu flauta. Verás en vivo qué nota detecta el modelo de{" "}
                  <strong>sonido de flauta</strong>, qué nota detecta el modelo de <strong>posición de manos</strong> y cuándo ambos coinciden.
                </p>
              </div>

              <Button
                type="button"
                className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-semibold py-2.5"
                onClick={() => void startFreeDetection()}
              >
                <Play className="w-4 h-4 mr-2 fill-current" />
                Iniciar Detección Libre en Vivo (Cámara + Micrófono)
              </Button>
            </div>
          )}

          {step === "setup" && mode === "exam" && (
            <div className="space-y-4">
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
                  Examen Nivel 1 (Principiante)
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
                  Examen Nivel 3 (Avanzado)
                </Button>
              </div>

              <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/5 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-sm font-bold text-foreground flex items-center gap-2">
                    <Music className="w-4 h-4 text-emerald-500" />
                    {targetLevel === 1
                      ? "Partitura Dinámica — Nivel 1 (1 Mano Arriba, Ritmo Pausado)"
                      : "Partitura Dinámica — Nivel 3 (Ambas Manos + FA# y Agudos)"}
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
                        ({seg.durationSec}s • {seg.handsRequired}M)
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <Button
                type="button"
                className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-semibold py-2.5"
                onClick={() => void startExamValidation()}
              >
                <Play className="w-4 h-4 mr-2 fill-current" />
                Iniciar Prueba de Nivel {targetLevel} (Encender Cámara y Micrófono)
              </Button>
            </div>
          )}

          {step === "playing" && mode === "free" && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
              {/* Panel Izquierdo: Detección Combinada + Cabeza Sonido + Cabeza Manos */}
              <div className="lg:col-span-5 space-y-3">
                {/* Veredicto combinado */}
                <div
                  className={`p-4 rounded-xl border-2 text-center space-y-1.5 transition-colors ${
                    modelInfo?.combined_match
                      ? "border-emerald-500 bg-emerald-500/15"
                      : "border-border bg-card"
                  }`}
                >
                  <span className="text-[11px] uppercase tracking-wider font-semibold text-muted-foreground block">
                    Detección Combinada (Sonido + Manos)
                  </span>
                  <div
                    className={`text-4xl font-extrabold ${
                      modelInfo?.combined_match
                        ? "text-emerald-600 dark:text-emerald-400"
                        : "text-muted-foreground"
                    }`}
                  >
                    {modelInfo?.combined_match && modelInfo.combined_note
                      ? formatNoteLabel(modelInfo.combined_note)
                      : "—"}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {modelInfo?.combined_match
                      ? "✓ Sonido de flauta y posición de manos coinciden"
                      : "Toca una nota frente a la cámara para confirmar sonido y digitación"}
                  </p>
                </div>

                {/* Cabeza 1: Sonido de Flauta */}
                <div className="p-3.5 rounded-xl border border-border bg-card space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold flex items-center gap-1.5">
                      <Volume2 className="w-4 h-4 text-emerald-500" />
                      Sonido de Flauta (Timbre)
                    </span>
                    <Badge
                      variant={
                        modelInfo?.sound_class === "NO_FLAUTA"
                          ? "secondary"
                          : "default"
                      }
                      className={
                        modelInfo && modelInfo.sound_class !== "NO_FLAUTA"
                          ? "bg-emerald-600 text-white font-mono"
                          : "font-mono"
                      }
                    >
                      {modelInfo
                        ? `${formatNoteLabel(modelInfo.sound_class)} (${Math.round(modelInfo.sound_confidence * 100)}%)`
                        : "Escuchando..."}
                    </Badge>
                  </div>
                  <Progress
                    value={Math.round((modelInfo?.sound_confidence ?? 0) * 100)}
                    className="h-2"
                  />
                  {modelInfo?.top_sound_classes && (
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {modelInfo.top_sound_classes.map((item) => (
                        <Badge
                          key={item.label}
                          variant="outline"
                          className="text-[10px] font-mono"
                        >
                          {formatNoteLabel(item.label)}: {Math.round(item.probability * 100)}%
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>

                {/* Cabeza 2: Posición de Manos */}
                <div className="p-3.5 rounded-xl border border-border bg-card space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold flex items-center gap-1.5">
                      <Hand className="w-4 h-4 text-sky-500" />
                      Posición de Manos
                    </span>
                    <Badge
                      variant={
                        !modelInfo?.posture_evaluable ||
                        modelInfo.posture_class === "INCORRECTA"
                          ? "secondary"
                          : "default"
                      }
                      className={
                        modelInfo?.posture_evaluable &&
                        modelInfo.posture_class !== "INCORRECTA"
                          ? "bg-sky-600 text-white font-mono"
                          : "font-mono"
                      }
                    >
                      {modelInfo?.posture_evaluable
                        ? `${formatNoteLabel(modelInfo.posture_class)} (${Math.round(modelInfo.posture_confidence * 100)}%)`
                        : "Sin manos / Inconcluso"}
                    </Badge>
                  </div>
                  <Progress
                    value={
                      modelInfo?.posture_evaluable
                        ? Math.round(modelInfo.posture_confidence * 100)
                        : 0
                    }
                    className="h-2"
                  />
                  {modelInfo?.posture_reason && (
                    <p className="text-[11px] text-amber-600 dark:text-amber-400">
                      {modelInfo.posture_reason}
                    </p>
                  )}
                  {modelInfo?.posture_evaluable && modelInfo.top_posture_classes && (
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {modelInfo.top_posture_classes.map((item) => (
                        <Badge
                          key={item.label}
                          variant="outline"
                          className="text-[10px] font-mono"
                        >
                          {formatNoteLabel(item.label)}: {Math.round(item.probability * 100)}%
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>

                {/* Historial de notas confirmadas */}
                {recentConfirmedNotes.length > 0 && (
                  <div className="p-3 rounded-xl border border-border bg-muted/30 space-y-1.5">
                    <span className="text-[11px] font-semibold text-muted-foreground block">
                      Últimas notas confirmadas (sonido + manos):
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {recentConfirmedNotes.map((note, idx) => (
                        <Badge
                          key={`${note}-${idx}`}
                          className="bg-emerald-600/90 text-white text-xs"
                        >
                          {FLUTE_NOTES_MAP[note].displayName}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                <Button
                  type="button"
                  variant="destructive"
                  size="sm"
                  className="w-full"
                  onClick={stopLiveSession}
                >
                  <Square className="w-3.5 h-3.5 mr-1.5 fill-current" />
                  Detener Detección en Vivo
                </Button>
              </div>

              {/* Panel Derecho: Cámara con Articulaciones de Manos */}
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

                  <FluteHandOverlay
                    videoRef={videoRef}
                    onFrame={(frame) => {
                      handFrameRef.current = frame
                    }}
                  />

                  <div className="absolute inset-0 p-3 flex flex-col justify-between pointer-events-none">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <Badge className="bg-black/80 text-white text-xs font-mono">
                        <Sun className="w-3.5 h-3.5 mr-1 text-amber-400" />
                        {cameraReady
                          ? "Cámara activa · Detección libre"
                          : "Iniciando cámara..."}
                      </Badge>

                      <Badge
                        className={
                          liveVoiceRejected
                            ? "bg-neutral-800 text-neutral-300 text-xs font-mono"
                            : liveDetectedNote
                            ? "bg-emerald-600 text-white text-xs font-mono"
                            : "bg-black/80 text-neutral-300 text-xs font-mono"
                        }
                      >
                        <Volume2 className="w-3.5 h-3.5 mr-1" />
                        {liveVoiceRejected
                          ? "Sin sonido de flauta"
                          : liveDetectedNote
                          ? `Flauta: ${FLUTE_NOTES_MAP[liveDetectedNote].displayName}`
                          : "Esperando sonido de flauta..."}
                      </Badge>
                    </div>

                    <div className="ml-auto mt-2 mb-auto w-36 flex flex-col gap-2">
                      <div
                        className={`rounded-lg px-3 py-2 text-center border-2 transition-colors text-xs font-bold ${
                          leftHandLive
                            ? "border-emerald-400 bg-emerald-950/65 text-emerald-200"
                            : "border-red-500/80 border-dashed bg-black/60 text-red-300"
                        }`}
                      >
                        {leftHandLive ? "Mano Izq detectada" : "Mano Izq ausente"}
                      </div>

                      <div
                        className={`rounded-lg px-3 py-2 text-center border-2 transition-colors text-xs font-bold ${
                          rightHandLive
                            ? "border-sky-400 bg-sky-950/65 text-sky-200"
                            : "border-neutral-500/60 border-dashed bg-black/45 text-neutral-300"
                        }`}
                      >
                        {rightHandLive ? "Mano Der detectada" : "Mano Der ausente"}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {step === "playing" && mode === "exam" && activeSegment && (
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

                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={stopLiveSession}
                >
                  <Square className="w-3.5 h-3.5 mr-1.5" />
                  Cancelar Prueba
                </Button>
              </div>

              {/* Cámara en Vivo */}
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

                  <FluteHandOverlay
                    videoRef={videoRef}
                    onFrame={(frame) => {
                      handFrameRef.current = frame
                    }}
                  />
                  <div className="absolute inset-0 p-3 flex flex-col justify-between pointer-events-none">
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
                            : liveDetectedNote
                            ? liveDetectedNote === activeSegment.targetNote
                              ? "bg-emerald-600 text-white text-xs font-mono"
                              : "bg-amber-600 text-white text-xs font-mono"
                            : "bg-black/80 text-neutral-300 text-xs font-mono"
                        }
                      >
                        <Volume2 className="w-3.5 h-3.5 mr-1" />
                        {liveVoiceRejected
                          ? "Sin sonido de flauta"
                          : liveDetectedNote
                          ? `Flauta: ${FLUTE_NOTES_MAP[liveDetectedNote].displayName}`
                          : "Esperando sonido de flauta..."}
                      </Badge>
                    </div>

                    <div className="ml-auto mt-2 mb-auto w-36 flex flex-col gap-2">
                      <div
                        className={`rounded-lg px-3 py-2 text-center border-2 transition-colors text-xs font-bold ${
                          leftHandLive
                            ? "border-emerald-400 bg-emerald-950/65 text-emerald-200"
                            : "border-red-500/80 border-dashed bg-black/60 text-red-300"
                        }`}
                      >
                        {leftHandLive
                          ? "Mano Izq detectada"
                          : "Mano Izq no detectada"}
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
                          ? "Mano Der detectada"
                          : activeNoteSpec.handsRequired === 2
                          ? "Mano Der no detectada"
                          : "Mano Der opcional"}
                      </div>
                    </div>

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
                          overallScore === null
                            ? "bg-amber-600 text-white"
                            : isApproved
                            ? "bg-emerald-600 text-white"
                            : "bg-destructive text-white"
                        }
                      >
                        {overallScore === null
                          ? "INCONCLUSO · NO SE PUNTÚA"
                          : isApproved
                          ? "APROBADO"
                          : "REQUIERE REVISIÓN"}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Coincidencia de sonido aprendido por timbre (75%) y digitación de manos aprendida (25%).
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
                    {overallScore === null
                      ? "Sin puntuación"
                      : `${overallScore} / 100`}
                  </span>
                </div>
              </div>

              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">#</TableHead>
                    <TableHead className="text-xs">Nota Pedida</TableHead>
                    <TableHead className="text-xs">Nota detectada (sonido)</TableHead>
                    <TableHead className="text-xs">Manos en Cámara</TableHead>
                    <TableHead className="text-xs text-right">
                      Coincidencia sonido
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
                        {FLUTE_NOTES_MAP[r.targetNote].displayName}
                      </TableCell>
                      <TableCell className="text-xs font-mono">
                        {r.detectedNote === r.targetNote ? (
                          <span className="text-emerald-600 dark:text-emerald-400 font-bold">
                            ✓ {formatNoteLabel(r.detectedNote)}
                          </span>
                        ) : (
                          <span className="text-destructive font-semibold">
                            ✗ {formatNoteLabel(r.detectedNote)}
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="text-xs">
                        {r.handPostureOk === null ? (
                          <Badge
                            variant="outline"
                            className="text-[10px] whitespace-normal border-amber-500 text-amber-700"
                          >
                            {r.handStatusLabel}
                          </Badge>
                        ) : r.handPostureOk ? (
                          <Badge
                            variant="outline"
                            className="border-emerald-500/40 text-emerald-600 text-[10px]"
                          >
                            <CheckCircle2 className="w-3 h-3 mr-1" />{" "}
                            {r.handStatusLabel}
                          </Badge>
                        ) : (
                          <Badge variant="destructive" className="text-[10px]">
                            <XCircle className="w-3 h-3 mr-1" />{" "}
                            {r.handStatusLabel}
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-xs font-mono text-right">
                        {r.soundScorePct}%
                      </TableCell>
                      <TableCell className="text-xs font-bold text-right">
                        {r.segmentTotalPct === null
                          ? "Inconcluso"
                          : `${r.segmentTotalPct}%`}
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
                  Volver al inicio
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

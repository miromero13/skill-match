import { useEffect, useMemo, useRef, useState } from "react"
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
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import {
  Video,
  Play,
  Square,
  CheckCircle2,
  Sparkles,
  Hand,
  SkipForward,
  Volume2,
} from "lucide-react"
import {
  FLUTE_NOTES_MAP,
  FLUTE_ORDERED_NOTES,
  FLUTE_VARIATIONS_LIST,
  RECOMMENDED_TAKES_PER_NOTE,
  extractFluteAudioFeatures,
  analyzeFluteAudioFrame,
  findClosestFluteNote,
  type FluteNoteName,
  type FluteVariationType,
} from "./flute-note-specs"
import {
  saveFluteLabels,
  type FluteLabels,
  type FluteFeatures,
  calculateFileSha256,
  uploadDatasetSample,
} from "@/services/dataset-sample-service"
import { useDatasetCaptureStore } from "@/stores/dataset-capture-store"
import type { DatasetSample } from "@/types/dataset-sample"

import { FluteHandOverlay } from "./flute-hand-overlay"
import { FLUTE_VISUAL_SCHEMA, freshHandFrame, type HandFrame } from "./flute-hand-features"

interface FluteGuidedCaptureProps {
  skillName: string
  samples: DatasetSample[]
  signedConsent: boolean
  hardwareInfo: string
  onSampleUploaded: () => Promise<void>
}

export function FluteGuidedCapture({
  skillName,
  samples,
  signedConsent,
  hardwareInfo,
  onSampleUploaded,
}: FluteGuidedCaptureProps) {
  const [participantId, setParticipantId] = useState("")
  const [soundLabel, setSoundLabel] = useState<FluteLabels["sound_label"]>("flauta")
  const [postureLabel, setPostureLabel] = useState<FluteLabels["posture_label"]>("correcta")
  const featureFramesRef = useRef<FluteFeatures[]>([])
  const handFrameRef = useRef<HandFrame | null>(null)
  const [selectedNote, setSelectedNote] = useState<FluteNoteName>("SI")
  const [selectedVariation, setSelectedVariation] =
    useState<FluteVariationType>("sostenida")
  const [continuousMode, setContinuousMode] = useState<boolean>(true)

  const [cameraActive, setCameraActive] = useState(false)
  const [countdown, setCountdown] = useState<number | null>(null)
  const [isRecordingClip, setIsRecordingClip] = useState(false)
  const [clipProgressPct, setClipProgressPct] = useState(0)
  const [isSavingClip, setIsSavingClip] = useState(false)
  const [statusBanner, setStatusBanner] = useState<string | null>(null)

  // Live audio & hand telemetry
  const [liveHz, setLiveHz] = useState<number | null>(null)
  const [detectedNote, setDetectedNote] = useState<FluteNoteName | null>(null)
  const [isInTune, setIsInTune] = useState(false)
  const [voiceRejected, setVoiceRejected] = useState(false)
  const [leftHandLive, setLeftHandLive] = useState(false)
  const [rightHandLive, setRightHandLive] = useState(false)
  const [lastPreviewUrl, setLastPreviewUrl] = useState<string | null>(null)

  const videoRef = useRef<HTMLVideoElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const measuredHzListRef = useRef<number[]>([])
  const continuousActiveRef = useRef<boolean>(false)
  const abortTimerRef = useRef<number | null>(null)

  const currentNoteSpec = FLUTE_NOTES_MAP[selectedNote]
  const currentVariationSpec =
    FLUTE_VARIATIONS_LIST.find((v) => v.id === selectedVariation) ||
    FLUTE_VARIATIONS_LIST[0]

  // Count how many samples exist per note in current dataset
  const noteCounts = useMemo(() => {
    const counts: Record<FluteNoteName, number> = {
      SI: 0,
      LA: 0,
      SOL: 0,
      DO6: 0,
      RE6: 0,
      FA: 0,
      "FA#": 0,
      MI: 0,
      RE: 0,
      DO: 0,
      MI6: 0,
    }
    const priorityNotes = [...FLUTE_ORDERED_NOTES].sort(
      (a, b) => b.length - a.length
    )
    for (const s of samples) {
      if (
        s.discipline.toLowerCase() !== "musica" &&
        s.discipline.toLowerCase() !== "música"
      ) {
        continue
      }
      const upperLabel = (s.level_label || "").toUpperCase()
      const upperChallenge = (s.challenge || "").toUpperCase()
      for (const note of priorityNotes) {
        if (
          upperLabel === note ||
          upperChallenge.includes(`NOTA ${note}`) ||
          upperChallenge.includes(`[${note}]`)
        ) {
          counts[note] += 1
          break
        }
      }
    }
    return counts
  }, [samples])

  const totalMusicSamples = useMemo(
    () =>
      Object.values(noteCounts).reduce((acc, c) => acc + c, 0),
    [noteCounts]
  )

  useEffect(() => {
    return () => {
      if (abortTimerRef.current) window.clearInterval(abortTimerRef.current)
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop())
      }
      if (audioCtxRef.current) {
        void audioCtxRef.current.close()
      }
    }
  }, [])

  useEffect(() => () => {
    if (lastPreviewUrl) URL.revokeObjectURL(lastPreviewUrl)
  }, [lastPreviewUrl])

  const ensureCameraAndMicStream = async (): Promise<MediaStream | null> => {
    if (streamRef.current && streamRef.current.active) {
      if (videoRef.current && videoRef.current.srcObject !== streamRef.current) {
        videoRef.current.srcObject = streamRef.current
      }
      return streamRef.current
    }
    try {
      const media = await navigator.mediaDevices.getUserMedia({
        video: { width: 1280, height: 720, facingMode: "user" },
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        },
      })
      streamRef.current = media
      setCameraActive(true)
      if (videoRef.current) {
        videoRef.current.srcObject = media
        void videoRef.current.play().catch(() => undefined)
      }

      // Attach real-time pitch detector & hand zone analyzer
      if (typeof window !== "undefined" && "AudioContext" in window) {
        const ctx = new window.AudioContext()
        audioCtxRef.current = ctx
        const source = ctx.createMediaStreamSource(media)
        const analyser = ctx.createAnalyser()
        analyser.fftSize = 2048
        source.connect(analyser)

        const pitchTimer = window.setInterval(() => {
          if (!streamRef.current || !streamRef.current.active) {
            window.clearInterval(pitchTimer)
            return
          }
          const frame = freshHandFrame(handFrameRef.current)
          const visualFeatures = frame?.features
          if (visualFeatures) {
            if (recorderRef.current?.state === "recording") {
              featureFramesRef.current.push({
                audio_features: extractFluteAudioFeatures(analyser, ctx.sampleRate),
                visual_features: visualFeatures,
                visual_schema: FLUTE_VISUAL_SCHEMA,
              })
            }
          }
          const audioInfo = analyzeFluteAudioFrame(analyser, ctx.sampleRate)
          if (audioInfo.isFluteTimbre && audioInfo.hz) {
            setLiveHz(audioInfo.hz)
            setVoiceRejected(false)
            const match = findClosestFluteNote(audioInfo.hz)
            setDetectedNote(match.note)
            setIsInTune(match.isInTune)
            measuredHzListRef.current.push(audioInfo.hz)
          } else if (audioInfo.rejectionReason === "voz_o_ruido") {
            setLiveHz(audioInfo.hz)
            setDetectedNote(null)
            setIsInTune(false)
            setVoiceRejected(true)
          } else {
            setLiveHz(null)
            setDetectedNote(null)
            setVoiceRejected(false)
          }

          setLeftHandLive(visualFeatures?.[0] === 1)
          setRightHandLive(visualFeatures?.[64] === 1)
        }, 160)
      }

      return media
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : "No se pudo abrir la cámara y el micrófono."
      useDatasetCaptureStore.setState({ error: msg })
      return null
    }
  }

  const getNextNoteAndVariation = (
    note: FluteNoteName,
    variation: FluteVariationType
  ): { nextNote: FluteNoteName; nextVar: FluteVariationType } => {
    const varOrder: FluteVariationType[] = ["sostenida", "rapida"]
    const currentVarIdx = varOrder.indexOf(variation)
    if (currentVarIdx !== -1 && currentVarIdx + 1 < varOrder.length) {
      return { nextNote: note, nextVar: varOrder[currentVarIdx + 1] }
    }
    const noteIdx = FLUTE_ORDERED_NOTES.indexOf(note)
    const nextNote =
      FLUTE_ORDERED_NOTES[(noteIdx + 1) % FLUTE_ORDERED_NOTES.length]
    return { nextNote, nextVar: "sostenida" }
  }

  const startGuidedTake = async (
    targetNote: FluteNoteName = selectedNote,
    targetVar: FluteVariationType = selectedVariation
  ) => {
    if (!participantId.trim()) {
      useDatasetCaptureStore.setState({ error: "Indica un ID estable por persona, no por nota ni toma." })
      return
    }
    if (!signedConsent) {
      useDatasetCaptureStore.setState({
        error:
          "Activa primero el interruptor de 'Consentimiento Informado Firmado' abajo antes de grabar.",
      })
      return
    }

    useDatasetCaptureStore.setState({ error: null })
    const stream = await ensureCameraAndMicStream()
    if (!stream) return
    if (!freshHandFrame(handFrameRef.current)) {
      setStatusBanner("Calibra el eje de la flauta sobre el video. Después pulsa Grabar otra vez.")
      return
    }

    continuousActiveRef.current = continuousMode

    // 1. 3-second preparation countdown
    let remainingCountdown = 3
    setCountdown(remainingCountdown)
    setStatusBanner(
      `Prepárate: Nota ${targetNote} (${
        FLUTE_VARIATIONS_LIST.find((v) => v.id === targetVar)?.shortLabel || targetVar
      }) — Coloca tus dedos en la flauta...`
    )

    const countInterval = window.setInterval(() => {
      remainingCountdown -= 1
      if (remainingCountdown > 0) {
        setCountdown(remainingCountdown)
      } else {
        window.clearInterval(countInterval)
        setCountdown(null)
        void recordFourSecondTake(stream, targetNote, targetVar)
      }
    }, 1000)
    abortTimerRef.current = countInterval
  }

  const recordFourSecondTake = async (
    stream: MediaStream,
    targetNote: FluteNoteName,
    targetVar: FluteVariationType
  ) => {
    measuredHzListRef.current = []
    featureFramesRef.current = []
    setIsRecordingClip(true)
    setClipProgressPct(0)

    const varSpec =
      FLUTE_VARIATIONS_LIST.find((v) => v.id === targetVar) ||
      FLUTE_VARIATIONS_LIST[0]
    const durationMs = varSpec.durationSeconds * 1000

    const mimeType =
      typeof MediaRecorder !== "undefined" &&
      MediaRecorder.isTypeSupported("video/mp4")
        ? "video/mp4"
        : "video/webm"

    const chunks: Blob[] = []
    const recorder = new MediaRecorder(stream, { mimeType })
    recorderRef.current = recorder

    recorder.ondataavailable = (ev) => {
      if (ev.data && ev.data.size > 0) {
        chunks.push(ev.data)
      }
    }

    const startTime = Date.now()
    const progressInterval = window.setInterval(() => {
      const elapsed = Date.now() - startTime
      const pct = Math.min(100, Math.round((elapsed / durationMs) * 100))
      setClipProgressPct(pct)
    }, 100)
    abortTimerRef.current = progressInterval

    recorder.onstop = async () => {
      window.clearInterval(progressInterval)
      setIsRecordingClip(false)
      setClipProgressPct(100)

      const clipBlob = new Blob(chunks, { type: "video/mp4" })
      if (lastPreviewUrl) URL.revokeObjectURL(lastPreviewUrl)
      setLastPreviewUrl(URL.createObjectURL(clipBlob))

      await uploadCapturedFluteClip(clipBlob, targetNote, targetVar)
    }

    recorder.start(250)
    setStatusBanner(`¡TOCA AHORA! Nota ${targetNote} — ${varSpec.instruction}`)

    window.setTimeout(() => {
      if (recorder.state !== "inactive") {
        recorder.stop()
      }
    }, durationMs)
  }

  const uploadCapturedFluteClip = async (
    blob: Blob,
    targetNote: FluteNoteName,
    targetVar: FluteVariationType
  ) => {
    setIsSavingClip(true)
    setStatusBanner(`Guardando muestra de Nota ${targetNote} (${targetVar})...`)
    try {
      const frames = featureFramesRef.current.filter(frame => postureLabel !== "correcta" ||
        frame.visual_features[0] + frame.visual_features[64] >= FLUTE_NOTES_MAP[targetNote].handsRequired)
      const features = frames[Math.floor(frames.length / 2)]
      if (!features || frames.length < 3) throw new Error("No hay 3 fotogramas con articulaciones suficientes. No se guardaron etiquetas; revisa el encuadre y la calibración.")
      const hash = await calculateFileSha256(blob)
      const avgMeasuredHz =
        measuredHzListRef.current.length > 0
          ? Math.round(
              measuredHzListRef.current.reduce((a, b) => a + b, 0) /
                measuredHzListRef.current.length
            )
          : null

      const fileName = `flauta-${targetNote.toLowerCase()}-${targetVar}-${Date.now()}.mp4`

      const res = await uploadDatasetSample({
        file: blob,
        fileName,
        discipline: "musica",
        challenge: `${skillName || "Flauta"} - Nota ${targetNote} (${targetVar})`,
        hardware_info: hardwareInfo.trim() || "Webcam + Micrófono Flauta en Vivo",
        signed_consent: true,
        file_hash_sha256: hash,
        participant_id: participantId.trim(),
        level_label: targetNote,
        manual_touch_count: avgMeasuredHz ?? undefined,
        noise_level: soundLabel,
        surface: targetVar,
        split: "train",
      })

      if (!res.data) throw new Error(res.message)
      const labels = await saveFluteLabels(res.data.id, {
        ...features,
        feature_frames: frames,
        participant_id: participantId.trim(),
        note_label: soundLabel === "flauta" || postureLabel === "correcta" ? targetNote : null,
        sound_label: soundLabel,
        posture_label: postureLabel,
      })
      useDatasetCaptureStore.setState({ lastUploadMessage: labels.message })
      await onSampleUploaded()

      const { nextNote, nextVar } = getNextNoteAndVariation(targetNote, targetVar)
      setSelectedNote(nextNote)
      setSelectedVariation(nextVar)

      if (continuousActiveRef.current) {
        setStatusBanner(
          `¡Nota ${targetNote} (${targetVar}) guardada! Pasando automáticamente a Nota ${nextNote} (${nextVar})...`
        )
        void startGuidedTake(nextNote, nextVar)
      } else {
        setStatusBanner(
          `¡Muestra guardada! Siguiente sugerida: Nota ${nextNote} (${nextVar}). Presiona Grabar cuando estés listo.`
        )
      }
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Error al guardar muestra de flauta."
      useDatasetCaptureStore.setState({ error: msg })
      setStatusBanner(null)
    } finally {
      setIsSavingClip(false)
    }
  }

  const stopGuidedSession = () => {
    continuousActiveRef.current = false
    if (abortTimerRef.current) {
      window.clearInterval(abortTimerRef.current)
      abortTimerRef.current = null
    }
    setCountdown(null)
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.stop()
    }
    setIsRecordingClip(false)
    setStatusBanner("Sesión continua pausada. Puedes retomar cuando quieras.")
  }

  return (
    <Card className="border-emerald-500/40 bg-emerald-500/5 shadow-sm">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <Badge className="bg-emerald-600 text-white text-xs">
                <Sparkles className="w-3.5 h-3.5 mr-1" />
                Entrenamiento Guiado de Flauta en Vivo
              </Badge>
              <Badge variant="outline" className="text-xs font-mono">
                {totalMusicSamples} muestras de flauta grabadas
              </Badge>
            </div>
            <CardTitle className="text-base sm:text-lg font-bold mt-1.5">
              Capturador de Notas y Posición de Manos (DO a SI + Agudos y FA#)
            </CardTitle>
            <CardDescription className="text-xs">
              Son 11 notas × 2 tomas obligatorias de 4s (1 Larga + 1 Rápida) ={" "}
              <strong>22 grabaciones cortas en total (~2 minutos)</strong>. El
              sistema te da 3 segundos entre toma y toma y avanza solo.
            </CardDescription>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <fieldset disabled={isRecordingClip || isSavingClip || countdown !== null} className="space-y-3">
          <Label htmlFor="flute-participant">ID estable de participante (misma persona = mismo ID)</Label>
          <Input id="flute-participant" value={participantId} onChange={e => setParticipantId(e.target.value)} placeholder="participante-01" />
          <p className="text-xs text-muted-foreground">Selecciona las etiquetas reales de la próxima toma, incluidos ejemplos negativos.</p>
          <div className="flex flex-wrap gap-2" role="group" aria-label="Etiqueta de sonido">
            {(["flauta", "voz", "ruido"] as const).map(label => (
              <Button key={label} variant={soundLabel === label ? "default" : "outline"} onClick={() => setSoundLabel(label)}>{label}</Button>
            ))}
          </div>
          <div className="flex flex-wrap gap-2" role="group" aria-label="Etiqueta de digitación">
            {(["correcta", "incorrecta", "sin_manos"] as const).map(label => (
              <Button key={label} variant={postureLabel === label ? "default" : "outline"} onClick={() => setPostureLabel(label)}>{label}</Button>
            ))}
          </div>
        </fieldset>
        {/* 1. Barra de las 11 Notas con contador de ejemplos grabados */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-foreground">
              Paso A —Las 11 Notas (meta: {RECOMMENDED_TAKES_PER_NOTE} tomas por nota = 22 en total):
            </span>
            <span className="text-muted-foreground font-mono text-[11px]">
              1 Mano: SI, LA, SOL, DO6, RE6 • 2 Manos: FA, FA#, MI, RE, DO, MI6
            </span>
          </div>
          <div className="grid grid-cols-3 sm:grid-cols-6 lg:grid-cols-11 gap-1.5">
            {FLUTE_ORDERED_NOTES.map((note) => {
              const count = noteCounts[note] || 0
              const isSelected = selectedNote === note
              const isComplete = count >= RECOMMENDED_TAKES_PER_NOTE
              const spec = FLUTE_NOTES_MAP[note]
              return (
                <Button
                  key={note}
                  type="button"
                  variant={isSelected ? "default" : "outline"}
                  size="sm"
                  onClick={() => setSelectedNote(note)}
                  className={`flex flex-col items-center justify-center h-auto py-2 px-1.5 ${
                    isSelected
                      ? "bg-emerald-600 hover:bg-emerald-700 text-white ring-2 ring-emerald-400"
                      : isComplete
                      ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                      : "bg-background/80"
                  }`}
                >
                  <div className="flex items-center gap-1 font-bold text-xs">
                    <span>{spec.displayName}</span>
                    {isComplete && <CheckCircle2 className="w-3 h-3" />}
                  </div>
                  <span className="text-[10px] opacity-85 font-mono">
                    {Math.round(spec.hz)}Hz • {count}/{RECOMMENDED_TAKES_PER_NOTE}
                  </span>
                </Button>
              )
            })}
          </div>
        </div>

        {/* 2. Selector de Variación (2 Obligatorias + 1 Extra Opcional) */}
        <div className="space-y-1.5">
          <span className="text-xs font-semibold text-foreground block">
            Paso B — Toma de la nota {currentNoteSpec.displayName} (2 tomas de 4s por nota: 1 Larga + 1 Rápida):
          </span>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            {FLUTE_VARIATIONS_LIST.map((v) => {
              const active = selectedVariation === v.id
              return (
                <Button
                  key={v.id}
                  type="button"
                  variant={active ? "default" : "outline"}
                  size="sm"
                  onClick={() => setSelectedVariation(v.id)}
                  className={
                    active
                      ? "bg-sky-600 hover:bg-sky-700 text-white text-xs font-semibold"
                      : "bg-background/80 text-xs"
                  }
                >
                  {v.shortLabel}
                </Button>
              )
            })}
          </div>
        </div>

        {/* 3. Tarjeta de Instrucción Activa + Diagrama Visual de Huecos y Manos */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-4 p-3.5 rounded-xl border border-border bg-card">
          {/* Diagrama de Flauta y Huecos */}
          <div className="md:col-span-5 flex flex-col justify-between space-y-3 border-b md:border-b-0 md:border-r border-border/60 pb-3 md:pb-0 md:pr-4">
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <Badge variant="secondary" className="text-xs font-bold">
                  NOTA {currentNoteSpec.displayName} ({Math.round(currentNoteSpec.hz)} Hz)
                </Badge>
                <Badge
                  variant="outline"
                  className={
                    currentNoteSpec.handsRequired === 2
                      ? "border-amber-500/50 text-amber-600 dark:text-amber-400 text-[11px]"
                      : "border-emerald-500/50 text-emerald-600 text-[11px]"
                  }
                >
                  <Hand className="w-3 h-3 mr-1" />
                  {currentNoteSpec.handsRequired === 2
                    ? "2 Manos (Izq Arriba + Der Abajo)"
                    : "1 Mano (Izq Arriba)"}
                </Badge>
              </div>
              <p className="text-xs font-medium text-foreground pt-1">
                {currentNoteSpec.handTip}
              </p>
              <p className="text-[11px] text-muted-foreground">
                <strong>Consigna:</strong> {currentVariationSpec.instruction}
              </p>
            </div>

            {/* Representación Visual de los 7 Huecos de la Flauta */}
            <div className="p-2.5 rounded-lg bg-muted/50 border border-border/60 space-y-2">
              <div className="flex items-center justify-between text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                <span>Digitar Flauta (● Tapado / ○ Libre)</span>
                <span>
                  Pulgar atrás:{" "}
                  {currentNoteSpec.thumbState === "tapado"
                    ? "● Tapado"
                    : currentNoteSpec.thumbState === "medio"
                    ? "◐ Medio (Agudo)"
                    : "○ Destapado"}
                </span>
              </div>
              <div className="flex items-center justify-between gap-1.5">
                {/* Mano Izquierda: Huecos 1, 2, 3 */}
                <div className="flex items-center gap-1.5 px-2 py-1.5 rounded bg-emerald-500/10 border border-emerald-500/30">
                  <span className="text-[10px] font-bold text-emerald-600 dark:text-emerald-400 mr-1">
                    Izq:
                  </span>
                  {currentNoteSpec.frontHoles.slice(0, 3).map((covered, i) => (
                    <div
                      key={`lh-${i}`}
                      title={`Hueco ${i + 1} (Mano Izquierda)`}
                      className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold border ${
                        covered
                          ? "bg-emerald-600 text-white border-emerald-500 shadow-xs"
                          : "bg-background text-muted-foreground border-border"
                      }`}
                    >
                      {i + 1}
                    </div>
                  ))}
                </div>

                {/* Mano Derecha: Huecos 4, 5, 6, 7 */}
                <div className="flex items-center gap-1.5 px-2 py-1.5 rounded bg-sky-500/10 border border-sky-500/30">
                  <span className="text-[10px] font-bold text-sky-600 dark:text-sky-400 mr-1">
                    Der:
                  </span>
                  {currentNoteSpec.frontHoles.slice(3, 7).map((covered, i) => (
                    <div
                      key={`rh-${i}`}
                      title={`Hueco ${i + 4} (Mano Derecha)`}
                      className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold border ${
                        covered
                          ? "bg-sky-600 text-white border-sky-500 shadow-xs"
                          : "bg-background text-muted-foreground border-border"
                      }`}
                    >
                      {i + 4}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Visor de Cámara en Vivo con HUD de Nota y Manos */}
          <div className="md:col-span-7 space-y-3">
            <div className="relative aspect-video rounded-lg overflow-hidden bg-neutral-950 border border-border flex items-center justify-center">
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
                className={`w-full h-full object-contain ${cameraActive ? "block" : "hidden"}`}
              />

              {cameraActive && <FluteHandOverlay videoRef={videoRef}
                onFrame={frame => { handFrameRef.current = frame }} />}

              {!cameraActive && (
                <div className="text-center p-6 text-muted-foreground space-y-2">
                  <Video className="w-10 h-10 mx-auto stroke-1 text-emerald-400 opacity-75" />
                  <p className="text-xs">
                    Presiona <strong>&ldquo;Grabar Toma Guiada (4s)&rdquo;</strong> para
                    activar cámara y micrófono con cuenta regresiva.
                  </p>
                </div>
              )}

              {/* Guías visuales de posición de manos sobre el video */}
              {cameraActive && (
                <div className="absolute inset-0 pointer-events-none flex flex-col justify-between p-3">
                  <div className="flex items-center justify-between">
                    <Badge className="bg-black/75 text-white border-white/20 text-xs font-mono">
                      Objetivo: {currentNoteSpec.displayName} ({Math.round(currentNoteSpec.hz)} Hz) •{" "}
                      {currentVariationSpec.shortLabel}
                    </Badge>
                    <Badge
                      className={
                        voiceRejected
                          ? "bg-red-600 text-white text-xs font-mono"
                          : liveHz
                          ? isInTune && detectedNote === selectedNote
                            ? "bg-emerald-600 text-white text-xs font-mono"
                            : "bg-amber-600 text-white text-xs font-mono"
                          : "bg-black/70 text-neutral-300 text-xs font-mono"
                      }
                    >
                      <Volume2 className="w-3.5 h-3.5 mr-1" />
                      {voiceRejected
                        ? "⚠️ Voz / Ruido rechazado (Usa la flauta)"
                        : liveHz
                        ? `Flauta: ${detectedNote} (${liveHz} Hz)`
                        : "Escuchando flauta..."}
                    </Badge>
                  </div>

                  {/* Marcos de detección real para Mano Izquierda (Arriba) y Derecha (Abajo) */}
                  <div className="ml-auto mt-2 mb-auto w-36 flex flex-col gap-1.5">
                    <div
                      className={`rounded px-2.5 py-1.5 text-center border-2 text-[11px] font-bold transition-colors ${
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
                      className={`rounded px-2.5 py-1.5 text-center border-2 text-[11px] font-bold transition-colors ${
                        rightHandLive
                          ? "border-sky-400 bg-sky-950/65 text-sky-200"
                          : currentNoteSpec.handsRequired === 2
                          ? "border-red-500/80 border-dashed bg-black/60 text-red-300"
                          : "border-neutral-500/60 border-dashed bg-black/45 text-neutral-300"
                      }`}
                    >
                      {rightHandLive
                        ? "Articulaciones B detectadas"
                        : currentNoteSpec.handsRequired === 2
                        ? "Mano B no detectada"
                        : "Mano B opcional"}
                    </div>
                  </div>

                  {isRecordingClip && (
                    <div className="space-y-1 bg-black/75 p-2 rounded-lg">
                      <div className="flex items-center justify-between text-xs text-white font-semibold">
                        <span className="flex items-center gap-1.5 text-red-400">
                          <span className="w-2 h-2 rounded-full bg-red-500 animate-ping" />
                          GRABANDO NOTA {selectedNote} ({currentVariationSpec.shortLabel})
                        </span>
                        <span className="font-mono">{clipProgressPct}%</span>
                      </div>
                      <Progress value={clipProgressPct} className="h-2" />
                    </div>
                  )}
                </div>
              )}

              {/* Cuenta regresiva gigante 3..2..1 */}
              {countdown !== null && (
                <div className="absolute inset-0 bg-black/65 flex flex-col items-center justify-center text-white space-y-2">
                  <span className="text-xs uppercase tracking-widest text-emerald-300 font-semibold">
                    Posiciona tus dedos para la nota {selectedNote}
                  </span>
                  <span className="text-6xl font-extrabold font-mono text-emerald-400 animate-pulse">
                    {countdown}
                  </span>
                  <span className="text-xs text-neutral-200">
                    {currentVariationSpec.title}
                  </span>
                </div>
              )}
            </div>

            {statusBanner && (
              <div className="p-2.5 rounded-lg bg-background border border-emerald-500/30 text-xs font-medium text-foreground flex items-center justify-between">
                <span>{statusBanner}</span>
              </div>
            )}

            {/* Controles de Grabación Guiada y Modo Continuo */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
              <div className="flex items-center gap-2">
                <Switch
                  id="continuous-flute-mode"
                  checked={continuousMode}
                  onCheckedChange={(checked) => {
                    setContinuousMode(checked)
                    continuousActiveRef.current = checked
                  }}
                />
                <Label
                  htmlFor="continuous-flute-mode"
                  className="text-xs font-semibold cursor-pointer"
                >
                  Avance Continuo (sin soltar la flauta entre tomas)
                </Label>
              </div>

              <div className="flex items-center gap-2">
                {countdown !== null || isRecordingClip ? (
                  <Button
                    type="button"
                    variant="destructive"
                    size="sm"
                    onClick={stopGuidedSession}
                  >
                    <Square className="w-4 h-4 mr-1.5 fill-current" />
                    Detener Sesión
                  </Button>
                ) : (
                  <>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={isSavingClip}
                      onClick={() => {
                        const { nextNote, nextVar } = getNextNoteAndVariation(
                          selectedNote,
                          selectedVariation
                        )
                        setSelectedNote(nextNote)
                        setSelectedVariation(nextVar)
                      }}
                    >
                      <SkipForward className="w-3.5 h-3.5 mr-1" />
                      Saltar a siguiente
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      disabled={isSavingClip}
                      onClick={() => void startGuidedTake(selectedNote, selectedVariation)}
                      className="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold"
                    >
                      <Play className="w-4 h-4 mr-1.5 fill-current" />
                      {isSavingClip
                        ? "Guardando muestra..."
                        : `Grabar Toma Guiada: ${selectedNote} (4s)`}
                    </Button>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

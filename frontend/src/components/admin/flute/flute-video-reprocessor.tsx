import { useEffect, useMemo, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Progress } from "@/components/ui/progress"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { getDatasetSampleContent, saveFluteLabels, type FluteFeatures, type FlutePreviewSample } from "@/services/dataset-sample-service"
import { FLUTE_MAX_FEATURE_FRAMES, extractFluteAudioFeatures } from "./flute-note-specs"
import { freshHandFrame, type HandFrame } from "./flute-hand-features"
import { FluteHandOverlay } from "./flute-hand-overlay"
import {
  LABELS_KEPT_SUFFIX, REPROCESS_STOPPED_REASON, collectReprocessFrame, describeReprocessProgress,
  finalizeReprocessTake, labeledFluteNote, reprocessItemTimeoutMs, runReprocessQueue, selectPendingReprocessSamples,
  type PitchCheckSummary, type ReprocessProgress, type ReprocessQueueSummary,
} from "./flute-reprocess-queue"

type AudioGraph = { ctx: AudioContext; analyser: AnalyserNode }
type Mode = "idle" | "single" | "batch"

function abortError(): DOMException {
  return new DOMException(REPROCESS_STOPPED_REASON, "AbortError")
}

function waitForMetadata(video: HTMLVideoElement, signal: AbortSignal): Promise<void> {
  if (signal.aborted) return Promise.reject(abortError())
  if (video.readyState >= 1) return Promise.resolve()
  return new Promise((resolve, reject) => {
    const cleanup = () => {
      video.removeEventListener("loadedmetadata", onLoaded)
      video.removeEventListener("error", onError)
      signal.removeEventListener("abort", onAbort)
    }
    const onLoaded = () => { cleanup(); resolve() }
    const onError = () => { cleanup(); reject(new Error("No se pudo cargar el video original.")) }
    const onAbort = () => { cleanup(); reject(abortError()) }
    video.addEventListener("loadedmetadata", onLoaded)
    video.addEventListener("error", onError)
    signal.addEventListener("abort", onAbort)
  })
}

export function FluteVideoReprocessor({ samples, onSaved }: { samples: FlutePreviewSample[]; onSaved: () => Promise<void> }) {
  // One video element, one hand overlay and one AudioContext/MediaElementSource for every take:
  // createMediaElementSource can only be called once per element, so takes swap `video.src`.
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const handRef = useRef<HandFrame | null>(null)
  const audioRef = useRef<AudioGraph | null>(null)
  const runRef = useRef<AbortController | null>(null)
  const [id, setId] = useState("")
  const [loadedId, setLoadedId] = useState<string | null>(null)
  const [stageActive, setStageActive] = useState(false)
  const [mode, setMode] = useState<Mode>("idle")
  const [message, setMessage] = useState("")
  const [count, setCount] = useState(0)
  const [pitchSummary, setPitchSummary] = useState<PitchCheckSummary | null>(null)
  const [progress, setProgress] = useState<ReprocessProgress | null>(null)
  const [summary, setSummary] = useState<ReprocessQueueSummary | null>(null)
  const pending = useMemo(() => selectPendingReprocessSamples(samples), [samples])
  const sample = samples.find(s => s.id === id)
  const activeSample = mode === "batch" ? progress?.sample ?? null : sample ?? null
  const activeNote = activeSample ? labeledFluteNote(activeSample) : null
  const isFluteTake = activeSample?.sound_label === "flauta"

  useEffect(() => () => {
    runRef.current?.abort()
    void audioRef.current?.ctx.close()
  }, [])

  useEffect(() => {
    if (!id) return
    let disposed = false
    void getDatasetSampleContent(id).then(response => {
      if (disposed) return
      const video = videoRef.current
      if (!response.data?.data_url || !video) { setMessage("El video original no está disponible."); return }
      video.muted = true
      video.src = response.data.data_url
      setLoadedId(id)
      setMessage("Reproduce el video para que se detecten las manos automáticamente y luego pulsa Reprocesar. Se conservan tus etiquetas originales.")
    }).catch((error: unknown) => { if (!disposed) setMessage(error instanceof Error ? error.message : "No se pudo cargar el video.") })
    // Recordings are cancelled by selectSample/unmount, not here: startBatch clears the selection.
    return () => { disposed = true }
  }, [id])

  const ensureAudioGraph = (video: HTMLVideoElement): AudioGraph => {
    if (!audioRef.current) {
      const ctx = new AudioContext()
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 2048
      const source = ctx.createMediaElementSource(video)
      source.connect(analyser)
      const gain = ctx.createGain()
      gain.gain.value = 0
      analyser.connect(gain)
      gain.connect(ctx.destination)
      audioRef.current = { ctx, analyser }
    }
    return audioRef.current
  }

  /** Plays the loaded take from the start in real time and collects gated frames until it ends. */
  const recordTake = async (
    take: FlutePreviewSample, signal: AbortSignal, onDuration?: (seconds: number) => void
  ): Promise<FluteFeatures[]> => {
    const video = videoRef.current
    if (!video) throw new Error("No hay un video cargado.")
    await waitForMetadata(video, signal)
    onDuration?.(video.duration)
    const audio = ensureAudioGraph(video)
    await audio.ctx.resume()
    if (signal.aborted) throw abortError()
    video.muted = false
    video.loop = false
    video.currentTime = 0
    handRef.current = null
    setCount(0)
    const frames: FluteFeatures[] = []
    await video.play()
    return new Promise((resolve, reject) => {
      const cleanup = () => {
        clearInterval(timer)
        video.removeEventListener("ended", onEnded)
        signal.removeEventListener("abort", onAbort)
      }
      const onEnded = () => { cleanup(); resolve(frames) }
      const onAbort = () => { cleanup(); video.pause(); reject(abortError()) }
      const timer = setInterval(() => {
        if (video.paused || video.seeking) return
        const frame = collectReprocessFrame(take, freshHandFrame(handRef.current)?.features ?? null,
          () => extractFluteAudioFeatures(audio.analyser, audio.ctx.sampleRate))
        if (!frame) return
        frames.push(frame)
        setCount(frames.length)
        if (frames.length >= FLUTE_MAX_FEATURE_FRAMES) { cleanup(); video.pause(); resolve(frames) }
      }, 160)
      video.addEventListener("ended", onEnded)
      signal.addEventListener("abort", onAbort)
      if (signal.aborted) onAbort()
    })
  }

  const selectSample = (value: string) => {
    runRef.current?.abort()
    setId(value)
    setLoadedId(null)
    setStageActive(true)
    setMessage("Cargando video guardado…")
    setCount(0)
    setPitchSummary(null)
  }

  const startSingle = async () => {
    const video = videoRef.current
    if (!sample || loadedId !== sample.id || !video) return
    if (!freshHandFrame(handRef.current)) { setMessage("Reproduce primero el video hasta que se detecten las manos y vuelve a pulsar Reprocesar."); return }
    const controller = new AbortController()
    runRef.current = controller
    setMode("single")
    setPitchSummary(null)
    setMessage("Extrayendo varios fotogramas del video original…")
    try {
      ensureAudioGraph(video)
      const frames = await recordTake(sample, controller.signal)
      const result = await finalizeReprocessTake(sample, frames, saveFluteLabels, controller.signal)
      setPitchSummary(result.pitch)
      if (result.ok) {
        setMessage(result.message)
        await onSaved()
      } else if (result.kind !== "cancelled") {
        setMessage(result.kind === "rejected" ? `${result.reason} ${LABELS_KEPT_SUFFIX}` : result.reason)
      }
    } catch (error: unknown) {
      if (!controller.signal.aborted) setMessage(error instanceof Error ? error.message : "No se pudo procesar el audio/video.")
    } finally {
      if (runRef.current === controller) runRef.current = null
      setMode("idle")
    }
  }

  const startBatch = async () => {
    const video = videoRef.current
    const queue = [...pending]
    if (!video || queue.length === 0) return
    runRef.current?.abort()
    const controller = new AbortController()
    runRef.current = controller
    setId("")
    setLoadedId(null)
    setStageActive(true)
    setMode("batch")
    setSummary(null)
    setPitchSummary(null)
    setMessage("")
    try {
      // Created inside the click so the browser allows audio for the unattended takes.
      void ensureAudioGraph(video).ctx.resume().catch(() => undefined)
    } catch { /* surfaced per item by recordTake */ }
    const result = await runReprocessQueue({
      samples: queue,
      signal: controller.signal,
      onSaved,
      onProgress: next => { setProgress(next); setCount(0); setPitchSummary(null) },
      processOne: async (take, signal, { setDeadline }) => {
        const response = await getDatasetSampleContent(take.id)
        if (signal.aborted) return { ok: false, reason: REPROCESS_STOPPED_REASON }
        if (!response.data?.data_url) return { ok: false, reason: "El video original no está disponible." }
        video.src = response.data.data_url
        const frames = await recordTake(take, signal, seconds => setDeadline(reprocessItemTimeoutMs(seconds)))
        // Batch: one summary at the end instead of a success toast per take.
        const outcome = await finalizeReprocessTake(take, frames,
          (sampleId, payload) => saveFluteLabels(sampleId, payload, { showToastOnSuccess: false }), signal)
        setPitchSummary(outcome.pitch)
        return outcome.ok ? { ok: true } : { ok: false, reason: outcome.reason }
      },
    })
    if (runRef.current === controller) runRef.current = null
    video.pause()
    setProgress(null)
    setSummary(result)
    setMode("idle")
  }

  const stageVisible = mode === "batch" || loadedId !== null
  return <Card>
    <CardHeader><CardTitle>Reutilizar videos guardados</CardTitle></CardHeader>
    <CardContent className="space-y-3">
      <p className="text-sm">No hace falta subirlos otra vez. Selecciona un video etiquetado, reprodúcelo para detectar las manos y extraer timbre + altura de audio (flute-audio-pitch-v1) y articulaciones de dedos (hand-landmarks-palm-v5). Se conservan participante y etiquetas.</p>
      <div className="flex flex-wrap items-center gap-3">
        <Button disabled={mode !== "idle" || pending.length === 0} onClick={() => void startBatch()}>
          Reprocesar todos los pendientes ({pending.length})
        </Button>
        <span className="text-xs text-muted-foreground">Procesa uno por uno, sin intervención, los MP4 en formato anterior con etiquetas revisadas.</span>
      </div>
      {mode === "batch" && progress && <div className="space-y-2" aria-live="polite">
        <p className="text-sm font-medium">{describeReprocessProgress(progress)}</p>
        <Progress value={((progress.index - 1) / progress.total) * 100} aria-label="Progreso del reprocesamiento" />
        <div className="flex items-center gap-3">
          <Button variant="destructive" onClick={() => runRef.current?.abort()}>Detener</Button>
          <span className="text-sm">{count} fotogramas{isFluteTake ? " con sonido" : ""}</span>
        </div>
      </div>}
      {summary && mode === "idle" && <BatchSummary summary={summary} />}
      <Select value={id} onValueChange={selectSample} disabled={mode !== "idle"}><SelectTrigger aria-label="Video para reprocesar"><SelectValue placeholder="Seleccionar video" /></SelectTrigger>
        <SelectContent>{samples.filter(s => s.file_format === "mp4" && s.sound_label && s.posture_label && s.participant_id).map(s =>
          <SelectItem key={s.id} value={s.id}>{s.participant_id} · {s.note_label ?? s.sound_label} · {s.id.slice(0, 8)} {s.labeled ? "(pitch-v1 + manos v5)" : s.needs_reprocess ? "(formato anterior: reprocesar)" : "(pendiente)"}</SelectItem>)}</SelectContent>
      </Select>
      {message && mode !== "batch" && sample && <Alert variant={pitchSummary?.rejected ? "destructive" : "default"}><AlertDescription>{message}</AlertDescription></Alert>}
      {pitchSummary && activeSample && <Alert variant={pitchSummary.rejected ? "destructive" : "default"}>
        <AlertDescription>Coincidencia de altura con la nota {activeNote}: {Math.round(pitchSummary.agreement * 100)}% ({pitchSummary.voicedFrames} fotogramas con sonido)</AlertDescription>
      </Alert>}
      <div className={stageVisible ? "relative aspect-video bg-black" : "hidden"}>
        <video ref={videoRef} playsInline controls={mode === "idle"} loop={mode === "idle"} muted className="h-full w-full object-contain" />
        {stageActive && <FluteHandOverlay videoRef={videoRef} onFrame={frame => { handRef.current = frame }} />}
      </div>
      {sample && mode !== "batch" && <div className="space-y-3">
        <Button variant="outline" disabled={loadedId !== sample.id || mode !== "idle"} onClick={() => {
          void videoRef.current?.play().catch(() => setMessage("No se pudo reproducir el video original."))
        }}>Reproducir video</Button>
        <Button disabled={loadedId !== sample.id || mode !== "idle"} onClick={() => void startSingle()}>Reprocesar conservando etiquetas</Button>
        <span className="ml-3 text-sm">{count} fotogramas{isFluteTake ? " con sonido" : ""}</span>
        <p className="text-xs text-muted-foreground">Extracción de articulaciones de manos relativas a la palma y muñeca sobre el video grabado.</p>
      </div>}
    </CardContent>
  </Card>
}

function BatchSummary({ summary }: { summary: ReprocessQueueSummary }) {
  return <Card>
    <CardHeader><CardTitle>Resumen del reprocesamiento</CardTitle></CardHeader>
    <CardContent className="space-y-2 text-sm">
      <p>Correctos: {summary.okCount} de {summary.total} · Rechazados o con error: {summary.failures.length}</p>
      {summary.stopped && <p>Detenido por el administrador: {summary.notProcessed} sin procesar (la toma en curso no se guardó).</p>}
      {summary.failures.length > 0 && <>
        <p className="text-muted-foreground">Las tomas rechazadas conservan sus etiquetas anteriores.</p>
        <Table>
          <TableHeader><TableRow>
            <TableHead>Nota</TableHead><TableHead>Participante</TableHead><TableHead>ID</TableHead><TableHead>Motivo</TableHead>
          </TableRow></TableHeader>
          <TableBody>{summary.failures.map(failure => <TableRow key={failure.id}>
            <TableCell>{failure.note}</TableCell>
            <TableCell>{failure.participant}</TableCell>
            <TableCell className="font-mono">{failure.shortId}</TableCell>
            <TableCell className="whitespace-normal">{failure.reason}</TableCell>
          </TableRow>)}</TableBody>
        </Table>
      </>}
    </CardContent>
  </Card>
}

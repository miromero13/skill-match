import { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { getDatasetSampleContent, saveFluteLabels, type FluteFeatures, type FlutePreviewSample } from "@/services/dataset-sample-service"
import { FLUTE_NOTES_MAP, extractFluteAudioFeatures, type FluteNoteName } from "./flute-note-specs"
import { FLUTE_VISUAL_SCHEMA, freshHandFrame, type HandFrame } from "./flute-hand-features"
import { FluteHandOverlay } from "./flute-hand-overlay"

export function FluteVideoReprocessor({ samples, onSaved }: { samples: FlutePreviewSample[]; onSaved: () => Promise<void> }) {
  const [id, setId] = useState("")
  const sample = samples.find(s => s.id === id)
  return <Card>
    <CardHeader><CardTitle>Reutilizar videos guardados</CardTitle></CardHeader>
    <CardContent className="space-y-3">
      <p className="text-sm">No hace falta subirlos otra vez. Selecciona un video etiquetado, calibra la flauta y vuelve a extraer sus articulaciones. Se conservan participante y etiquetas.</p>
      <Select value={id} onValueChange={setId}><SelectTrigger aria-label="Video para reprocesar"><SelectValue placeholder="Seleccionar video" /></SelectTrigger>
        <SelectContent>{samples.filter(s => s.file_format === "mp4" && s.sound_label && s.posture_label && s.participant_id).map(s =>
          <SelectItem key={s.id} value={s.id}>{s.participant_id} · {s.note_label ?? s.sound_label} · {s.id.slice(0, 8)} {s.labeled ? "(articulaciones)" : "(pendiente)"}</SelectItem>)}</SelectContent>
      </Select>
      {sample && <ReprocessVideo key={sample.id} sample={sample} onSaved={onSaved} />}
    </CardContent>
  </Card>
}

function ReprocessVideo({ sample, onSaved }: { sample: FlutePreviewSample; onSaved: () => Promise<void> }) {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const handRef = useRef<HandFrame | null>(null)
  const audioRef = useRef<{ ctx: AudioContext; analyser: AnalyserNode } | null>(null)
  const framesRef = useRef<FluteFeatures[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined)
  const processingRef = useRef(false)
  const [url, setUrl] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState("Cargando video guardado…")
  const [count, setCount] = useState(0)
  useEffect(() => {
    let disposed = false
    void getDatasetSampleContent(sample.id).then(response => {
      if (disposed) return
      if (!response.data?.data_url) { setMessage("El video original no está disponible."); return }
      setUrl(response.data.data_url)
      setMessage("Reproduce el video y calibra la flauta. Luego pulsa Reprocesar. La extracción conserva tus etiquetas, no las predice.")
    }).catch((error: unknown) => { if (!disposed) setMessage(error instanceof Error ? error.message : "No se pudo cargar el video.") })
    return () => {
      disposed = true
      processingRef.current = false
      clearInterval(timerRef.current)
      void audioRef.current?.ctx.close()
    }
  }, [sample.id])

  const finish = async () => {
    if (!processingRef.current) return
    processingRef.current = false
    clearInterval(timerRef.current)
    try {
      const frames = framesRef.current
      if (frames.length < 3) throw new Error("No se detectaron suficientes articulaciones. No se modificaron las etiquetas anteriores.")
      if (!sample.participant_id || !sample.sound_label || !sample.posture_label) throw new Error("Faltan etiquetas revisadas.")
      const response = await saveFluteLabels(sample.id, { ...frames[Math.floor(frames.length / 2)],
        feature_frames: frames, participant_id: sample.participant_id, note_label: sample.note_label,
        sound_label: sample.sound_label, posture_label: sample.posture_label })
      setMessage(response.message)
      await onSaved()
    } catch (error: unknown) { setMessage(error instanceof Error ? error.message : "No se pudo reprocesar.") }
    finally { setBusy(false) }
  }

  const start = async () => {
    const video = videoRef.current
    if (!video || !freshHandFrame(handRef.current)) { setMessage("Reproduce el video y calibra primero el eje de la flauta."); return }
    try {
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
      await audioRef.current.ctx.resume()
      video.muted = false
      video.loop = false
      video.currentTime = 0
      handRef.current = null
      framesRef.current = []
      setCount(0)
      setBusy(true)
      processingRef.current = true
      await video.play()
      timerRef.current = setInterval(() => {
        const frame = freshHandFrame(handRef.current)
        const audio = audioRef.current
        if (!frame || !audio || video.paused || video.seeking) return
        const required = sample.note_label && Object.hasOwn(FLUTE_NOTES_MAP, sample.note_label)
          ? FLUTE_NOTES_MAP[sample.note_label as FluteNoteName].handsRequired : 1
        if (sample.posture_label === "correcta" && frame.features[0] + frame.features[64] < required) return
        framesRef.current.push({ visual_schema: FLUTE_VISUAL_SCHEMA, visual_features: frame.features,
          audio_features: extractFluteAudioFeatures(audio.analyser, audio.ctx.sampleRate) })
        setCount(framesRef.current.length)
        if (framesRef.current.length >= 120) { video.pause(); void finish() }
      }, 160)
      setMessage("Extrayendo varios fotogramas del video original…")
    } catch (error: unknown) {
      processingRef.current = false
      setBusy(false)
      setMessage(error instanceof Error ? error.message : "No se pudo procesar el audio/video.")
    }
  }

  return <div className="space-y-3">
    <Alert><AlertDescription>{message}</AlertDescription></Alert>
    {url && <div className="relative aspect-video bg-black">
      <video ref={videoRef} src={url} playsInline controls={!busy} loop={!busy} muted className="h-full w-full object-contain" onEnded={() => void finish()} />
      <FluteHandOverlay videoRef={videoRef} onFrame={frame => { handRef.current = frame }} />
    </div>}
    <Button variant="outline" disabled={!url || busy} onClick={() => {
      void videoRef.current?.play().catch(() => setMessage("No se pudo reproducir el video original."))
    }}>Reproducir video</Button>
    <Button disabled={!url || busy} onClick={() => void start()}>Reprocesar conservando etiquetas</Button>
    <span className="ml-3 text-sm">{count} fotogramas</span>
    <p className="text-xs text-muted-foreground">Extracción de articulaciones de manos relativas a la palma y muñeca sobre el video grabado.</p>
  </div>
}

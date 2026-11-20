import { useCallback, useEffect, useRef, useState, type RefObject } from "react"
import { AlertTriangle, Award, Music, Play, RotateCcw, Square } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  listFluteSongs,
  scoreFluteSong,
  type FlutePitchSample,
  type FluteSong,
  type FluteSongNoteResult,
  type FluteSongScore,
  type FluteTimedFeatures,
} from "@/services/flute-song-service"
import { estimatePitchYin, extractFluteAudioFeatures } from "./flute-note-specs"
import { freshHandFrame, type HandFrame } from "./flute-hand-features"
import {
  COUNT_IN_BEATS,
  CAPTURE_PRE_ROLL_S,
  SONG_MAX_BPM,
  SONG_MIN_BPM,
  buildScoreSongPayload,
  captureEndSeconds,
  clampSongTempo,
  computeRms,
  countInBeatAt,
  countInSchedule,
  currentNoteIndex,
  fingeringLabel,
  groupSongStrip,
  noteChipStatus,
  noteDisplayName,
  onsetLabel,
  passLabel,
  songProgressPct,
} from "./flute-song-timeline"

/** Media already opened by the live validator (one camera + one mic for every mode). */
export interface SongCaptureDevices {
  audioContext: AudioContext
  analyser: AnalyserNode
  sampleRate: number
}

interface FluteSongPracticeProps {
  /** Devices currently open in the validator, or null when the camera/mic are off. */
  devices: SongCaptureDevices | null
  /** Opens the validator's camera + mic when needed; null when it failed (validator shows the error). */
  requestDevices: () => Promise<SongCaptureDevices | null>
  handFrameRef: RefObject<HandFrame | null>
}

type PracticePhase = "idle" | "starting" | "countin" | "playing" | "scoring" | "result"

const PITCH_INTERVAL_MS = 25
const FEATURE_INTERVAL_MS = 100
const UI_INTERVAL_MS = 50
/** Small lead so the first click is never scheduled in the past. */
const COUNT_IN_LEAD_S = 0.15
const NO_POSTURE_TEXT =
  "Digitación no evaluable (sin modelo o sin datos de estas notas)"

interface ActiveRun {
  intervals: number[]
  clickNodes: AudioScheduledSourceNode[]
}

/**
 * Count-in click: a short decaying noise burst. Noise has no pitch, so the clicks that the
 * microphone hears in the last second of the count-in are never taken as a voiced flute onset.
 */
function scheduleClicks(ctx: AudioContext, times: number[]): ActiveRun["clickNodes"] {
  const length = Math.max(1, Math.floor(ctx.sampleRate * 0.04))
  const buffer = ctx.createBuffer(1, length, ctx.sampleRate)
  const data = buffer.getChannelData(0)
  for (let i = 0; i < length; i++) {
    data[i] = (Math.random() * 2 - 1) * Math.exp(-i / (ctx.sampleRate * 0.006))
  }
  return times.map((at, i) => {
    const source = ctx.createBufferSource()
    source.buffer = buffer
    const accent = ctx.createGain()
    accent.gain.value = i === 0 ? 0.9 : 0.55
    source.connect(accent)
    accent.connect(ctx.destination)
    source.start(at)
    return source
  })
}

function chipClass(status: ReturnType<typeof noteChipStatus>, active: boolean): string {
  const base = "min-w-10 justify-center font-semibold transition-all"
  const ring = active ? " ring-2 ring-emerald-500 ring-offset-1 scale-110" : ""
  if (status === "correct") return `${base} bg-emerald-600 text-white${ring}`
  if (status === "wrong") return `${base} bg-destructive text-white${ring}`
  return `${base} bg-muted text-muted-foreground${ring}`
}

interface FluteSongStripProps {
  song: FluteSong
  activeIndex: number | null
  results?: readonly FluteSongNoteResult[]
}

/** S3: the 30-note strip grouped by pass and bar; current note highlighted, results colored. */
export function FluteSongStrip({ song, activeIndex, results = [] }: FluteSongStripProps) {
  const byIndex = new Map(results.map((r) => [r.index, r]))
  return (
    <div className="space-y-2" data-testid="flute-song-strip">
      {groupSongStrip(song).map((group) => (
        <div key={group.pass} className="space-y-1">
          <span className="text-[11px] font-semibold text-muted-foreground">
            {group.label}
          </span>
          <div className="flex flex-wrap gap-2">
            {group.bars.map((bar) => (
              <div
                key={bar.bar}
                className="flex flex-wrap items-center gap-1 rounded-lg border border-border/60 px-1.5 py-1"
              >
                {bar.notes.map((note) => {
                  const status = noteChipStatus(byIndex.get(note.index))
                  return (
                    <Badge
                      key={note.index}
                      data-testid={`flute-song-chip-${note.index}`}
                      data-status={status}
                      data-active={activeIndex === note.index ? "true" : "false"}
                      className={chipClass(status, activeIndex === note.index)}
                    >
                      {noteDisplayName(note.note)}
                    </Badge>
                  )
                })}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

function entryLabel(r: FluteSongNoteResult): string {
  if (r.repeated && r.articulation_ok === false) {
    return "sin separar de la nota anterior"
  }
  return onsetLabel(r.onset_ms)
}

/** S4: summary + per-note verdict table. */
export function FluteSongResultView({ score }: { score: FluteSongScore }) {
  return (
    <div className="space-y-4">
      <Card size="sm">
        <CardContent className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <Award
              className={`h-10 w-10 shrink-0 ${
                score.approved ? "text-emerald-500" : "text-destructive"
              }`}
            />
            <div className="space-y-1">
              <p className="text-sm font-semibold">
                Notas correctas: {score.notes_correct} / {score.notes_total}
              </p>
              <p className="text-xs text-muted-foreground">
                Sonido: {Math.round(score.sound_score)} / 100
              </p>
              <p className="text-xs text-muted-foreground">
                {score.posture_score === null
                  ? NO_POSTURE_TEXT
                  : `Digitación: ${Math.round(score.posture_score)} / 100`}
              </p>
              <p className="text-[11px] text-muted-foreground">
                {score.model_version
                  ? `Modelo ${score.model_version}`
                  : "Sin modelo activo: solo altura del sonido"}{" "}
                · Latencia corregida {Math.round(score.latency_offset_ms)} ms
              </p>
            </div>
          </div>
          <div className="flex flex-col items-start gap-2 sm:items-end">
            <span className="text-3xl font-extrabold">
              {Math.round(score.total_score)} / 100
            </span>
            <Badge
              data-testid="flute-song-verdict"
              className={`h-8 px-4 text-base ${
                score.approved
                  ? "bg-emerald-600 text-white"
                  : "bg-destructive text-white"
              }`}
            >
              {score.approved ? "Aprobado" : "Reprobado"}
            </Badge>
          </div>
        </CardContent>
      </Card>

      {score.message && (
        <Alert>
          <AlertDescription>{score.message}</AlertDescription>
        </Alert>
      )}

      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="text-xs">#</TableHead>
              <TableHead className="text-xs">Vuelta</TableHead>
              <TableHead className="text-xs">Nota esperada</TableHead>
              <TableHead className="text-xs">Detectada</TableHead>
              <TableHead className="text-xs">Tiempo de entrada</TableHead>
              <TableHead className="text-xs">Dedos</TableHead>
              <TableHead className="text-xs">Resultado</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {score.notes.map((r) => (
              <TableRow key={r.index} data-testid={`flute-song-row-${r.index}`}>
                <TableCell className="font-mono text-xs">{r.index + 1}</TableCell>
                <TableCell className="text-xs">{passLabel(r.pass)}</TableCell>
                <TableCell className="text-xs font-bold">
                  {noteDisplayName(r.note)}
                </TableCell>
                <TableCell
                  className={`text-xs ${
                    r.detected_note === r.note ? "" : "font-semibold text-destructive"
                  }`}
                >
                  {noteDisplayName(r.detected_note)}
                </TableCell>
                <TableCell
                  className={`text-xs ${
                    r.timing_ok === false ? "text-destructive" : ""
                  }`}
                >
                  {entryLabel(r)}
                </TableCell>
                <TableCell className="text-xs">
                  <span
                    className={
                      r.posture_ok === false
                        ? "font-semibold text-destructive"
                        : r.posture_ok === true
                        ? "font-semibold text-emerald-600 dark:text-emerald-400"
                        : "text-muted-foreground"
                    }
                    title={r.posture_reason ?? undefined}
                  >
                    {fingeringLabel(r.posture_ok)}
                  </span>
                  {r.mismatched_holes.length > 0 && (
                    <span className="block text-[10px] text-destructive">
                      Huecos: {r.mismatched_holes.join(", ")}
                    </span>
                  )}
                </TableCell>
                <TableCell className="text-xs">
                  <Badge
                    variant={r.correct ? "outline" : "destructive"}
                    className={
                      r.correct ? "border-emerald-500 text-emerald-700 dark:text-emerald-300" : ""
                    }
                  >
                    {r.correct ? "✓ Correcta" : "✗ Incorrecta"}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

/** S1/S3/S4/S5: «Canción» mode — count-in, capture, scoring and verdict for a whole song. */
export function FluteSongPractice({
  devices,
  requestDevices,
  handFrameRef,
}: FluteSongPracticeProps) {
  const [songs, setSongs] = useState<FluteSong[]>([])
  const [songsLoading, setSongsLoading] = useState(true)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [tempo, setTempo] = useState(120)
  const [phase, setPhase] = useState<PracticePhase>("idle")
  const [countBeat, setCountBeat] = useState<number | null>(null)
  const [activeIndex, setActiveIndex] = useState<number | null>(null)
  const [progress, setProgress] = useState(0)
  const [score, setScore] = useState<FluteSongScore | null>(null)
  const [error, setError] = useState<string | null>(null)

  const generationRef = useRef(0)
  const runRef = useRef<ActiveRun | null>(null)
  const prevDevicesRef = useRef<SongCaptureDevices | null>(devices)

  const song = songs.find((s) => s.id === selectedId) ?? null

  useEffect(() => {
    let cancelled = false
    listFluteSongs()
      .then((res) => {
        if (cancelled) return
        const list = res.data ?? []
        setSongs(list)
        const first = list[0]
        if (first) {
          setSelectedId(first.id)
          setTempo(clampSongTempo(first.default_bpm))
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(
          err instanceof Error ? err.message : "No se pudo cargar el catálogo de canciones."
        )
      })
      .finally(() => {
        if (!cancelled) setSongsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const stopRun = useCallback(() => {
    const run = runRef.current
    runRef.current = null
    if (!run) return
    run.intervals.forEach((id) => window.clearInterval(id))
    for (const node of run.clickNodes) {
      try {
        node.stop()
      } catch {
        // already finished
      }
      node.disconnect()
    }
  }, [])

  const resetLiveView = () => {
    setCountBeat(null)
    setActiveIndex(null)
    setProgress(0)
  }

  const cancel = useCallback(() => {
    generationRef.current += 1
    stopRun()
    setCountBeat(null)
    setActiveIndex(null)
    setProgress(0)
    setPhase("idle")
  }, [stopRun])

  useEffect(() => () => {
    generationRef.current += 1
    stopRun()
  }, [stopRun])

  // The validator turned the camera/mic off: abort any running take.
  useEffect(() => {
    const prev = prevDevicesRef.current
    prevDevicesRef.current = devices
    if (prev && !devices && runRef.current) cancel()
  }, [devices, cancel])

  const start = async () => {
    if (!song) return
    const generation = ++generationRef.current
    stopRun()
    setError(null)
    setScore(null)
    resetLiveView()
    setPhase("starting")

    const media = devices ?? (await requestDevices())
    if (generation !== generationRef.current) return
    if (!media) {
      setPhase("idle")
      return
    }
    const { audioContext: ctx, analyser, sampleRate } = media
    if (ctx.state === "suspended") {
      await ctx.resume().catch(() => undefined)
      if (generation !== generationRef.current) return
    }

    const bpm = clampSongTempo(tempo)
    const beat = 60 / bpm
    const t0 = ctx.currentTime + COUNT_IN_LEAD_S + COUNT_IN_BEATS * beat
    const endS = captureEndSeconds(song, bpm)
    const pitchTrack: FlutePitchSample[] = []
    const audioFrames: FluteTimedFeatures[] = []
    const handFrames: FluteTimedFeatures[] = []
    const waveform = new Float32Array(analyser.fftSize)
    const now = () => ctx.currentTime - t0

    const run: ActiveRun = {
      intervals: [],
      clickNodes: scheduleClicks(
        ctx,
        countInSchedule(bpm).map((t) => t0 + t)
      ),
    }
    runRef.current = run

    const finish = async () => {
      stopRun()
      resetLiveView()
      setProgress(100)
      setPhase("scoring")
      try {
        const res = await scoreFluteSong(
          buildScoreSongPayload({ song, tempoBpm: bpm, pitchTrack, audioFrames, handFrames })
        )
        if (generation !== generationRef.current) return
        if (!res.data) throw new Error(res.message)
        setScore(res.data)
        setPhase("result")
      } catch (err: unknown) {
        if (generation !== generationRef.current) return
        setError(err instanceof Error ? err.message : "No se pudo calificar la canción.")
        setPhase("idle")
      }
    }

    run.intervals.push(
      window.setInterval(() => {
        const t = now()
        if (t < -CAPTURE_PRE_ROLL_S || t > endS) return
        analyser.getFloatTimeDomainData(waveform)
        const { hz, clarity } = estimatePitchYin(waveform, sampleRate)
        pitchTrack.push({ t, hz, clarity, rms: computeRms(waveform) })
      }, PITCH_INTERVAL_MS),
      window.setInterval(() => {
        const t = now()
        if (t < -CAPTURE_PRE_ROLL_S || t > endS) return
        audioFrames.push({ t, features: extractFluteAudioFeatures(analyser, sampleRate) })
        const frame = freshHandFrame(handFrameRef.current)
        if (frame) handFrames.push({ t, features: [...frame.features] })
      }, FEATURE_INTERVAL_MS),
      window.setInterval(() => {
        const t = now()
        if (t >= endS) {
          void finish()
          return
        }
        if (t < 0) {
          setPhase("countin")
          setCountBeat(countInBeatAt(bpm, t))
          return
        }
        setPhase("playing")
        setCountBeat(null)
        setActiveIndex(currentNoteIndex(song, bpm, t))
        setProgress(songProgressPct(song, bpm, t))
      }, UI_INTERVAL_MS)
    )
    setPhase("countin")
  }

  const running = phase === "starting" || phase === "countin" || phase === "playing"
  const activeNote =
    song && activeIndex !== null ? song.notes.find((n) => n.index === activeIndex) : undefined

  return (
    <Card className="border-border/60 shadow-sm">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <Music className="h-4 w-4 text-emerald-500" />
          Canción
        </CardTitle>
        <CardDescription className="text-xs">
          Elige una canción, ajusta el tempo y pulsa «Empezar». Escucharás 4 pulsos de cuenta y luego tocas la partitura completa sin clics. Al final verás qué notas tocaste bien o mal.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>No se pudo completar la canción</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {!songsLoading && songs.length === 0 && !error && (
          <Alert>
            <AlertDescription>No hay canciones disponibles.</AlertDescription>
          </Alert>
        )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="flute-song-select" className="text-xs">
              Canción
            </Label>
            <Select
              value={selectedId ?? undefined}
              onValueChange={(id) => {
                setSelectedId(id)
                setScore(null)
                const next = songs.find((s) => s.id === id)
                if (next) setTempo(clampSongTempo(next.default_bpm))
              }}
              disabled={running || phase === "scoring" || songs.length === 0}
            >
              <SelectTrigger id="flute-song-select" aria-label="Canción" className="w-full">
                <SelectValue placeholder={songsLoading ? "Cargando canciones..." : "Seleccionar canción"} />
              </SelectTrigger>
              <SelectContent>
                {songs.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-3">
            <Label className="text-xs">Tempo: {tempo} BPM</Label>
            <Slider
              aria-label="Tempo"
              min={song?.min_bpm ?? SONG_MIN_BPM}
              max={song?.max_bpm ?? SONG_MAX_BPM}
              step={1}
              value={[tempo]}
              onValueChange={(v) => setTempo(clampSongTempo(v[0] ?? tempo))}
              disabled={running || phase === "scoring" || !song}
            />
          </div>
        </div>

        {song && (
          <img
            src={song.image}
            alt={`Partitura: ${song.title}`}
            className="h-auto max-h-[420px] w-full rounded-lg border border-border bg-white object-contain"
          />
        )}

        {phase === "countin" && (
          <div
            className="flex items-center justify-center gap-4 py-2 sm:gap-6"
            data-testid="flute-song-countin"
            aria-live="polite"
          >
            {Array.from({ length: COUNT_IN_BEATS }, (_, i) => i + 1).map((n) => (
              <span
                key={n}
                className={`text-4xl font-extrabold tabular-nums transition-all sm:text-6xl ${
                  countBeat === n
                    ? "scale-125 text-emerald-600 dark:text-emerald-400"
                    : "text-muted-foreground/40"
                }`}
              >
                {n}
              </span>
            ))}
          </div>
        )}

        {(phase === "playing" || phase === "scoring") && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">
                {phase === "scoring" ? "Calificando..." : "Toca ahora:"}
              </span>
              <span className="text-2xl font-extrabold text-emerald-600 dark:text-emerald-400">
                {activeNote ? noteDisplayName(activeNote.note) : ""}
              </span>
            </div>
            <Progress value={progress} className="h-2.5" />
          </div>
        )}

        {song && (
          <FluteSongStrip
            song={song}
            activeIndex={phase === "playing" ? activeIndex : null}
            results={phase === "result" && score ? score.notes : []}
          />
        )}

        <div className="flex flex-wrap gap-2">
          {(phase === "idle" || phase === "scoring") && (
            <Button
              type="button"
              className="bg-emerald-600 text-white hover:bg-emerald-700"
              disabled={!song || phase === "scoring"}
              onClick={() => void start()}
            >
              <Play className="mr-2 h-4 w-4 fill-current" />
              Empezar
            </Button>
          )}
          {running && (
            <Button type="button" variant="destructive" onClick={cancel}>
              <Square className="mr-2 h-4 w-4 fill-current" />
              Detener
            </Button>
          )}
          {phase === "result" && (
            <Button type="button" variant="outline" onClick={() => void start()}>
              <RotateCcw className="mr-2 h-4 w-4" />
              Repetir
            </Button>
          )}
        </div>

        {phase === "result" && score && <FluteSongResultView score={score} />}
      </CardContent>
    </Card>
  )
}

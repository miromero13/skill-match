import { FLUTE_AUDIO_SCHEMA } from "./flute-note-specs"
import { FLUTE_VISUAL_SCHEMA } from "./flute-hand-features"
import type {
  FlutePitchSample,
  FluteSong,
  FluteSongNote,
  FluteSongNoteResult,
  FluteSongPass,
  FluteTimedFeatures,
  ScoreFluteSongPayload,
} from "@/services/flute-song-service"

/** S5: audible count-in beats before t0 (no clicks while playing). */
export const COUNT_IN_BEATS = 4
/** Contract caps for the score-song payload. */
export const PITCH_TRACK_MAX = 4000
export const AUDIO_FRAMES_MAX = 1000
export const HAND_FRAMES_MAX = 1000
/** Samples kept before t0 (lets the backend see an early first onset). */
export const CAPTURE_PRE_ROLL_S = 1.0
/** Capture continues this long after the last note ends. */
export const CAPTURE_TAIL_S = 0.5
export const SONG_MIN_BPM = 60
export const SONG_MAX_BPM = 120
/** Onsets closer than one capture frame (~25 ms) to the beat are shown as "a tiempo". */
export const ON_TIME_TOLERANCE_MS = 25

type SongTimeline = Pick<FluteSong, "notes">

export function beatSeconds(bpm: number): number {
  return 60 / bpm
}

export function beatsToSeconds(beats: number, bpm: number): number {
  return (beats * 60) / bpm
}

/** Seconds from t0 to the end of the last note. */
export function songDurationSeconds(song: SongTimeline, bpm: number): number {
  const endBeats = song.notes.reduce(
    (max, n) => Math.max(max, n.start_beats + n.duration_beats),
    0
  )
  return beatsToSeconds(endBeats, bpm)
}

/** Capture stops automatically at last note end + 0.5 s. */
export function captureEndSeconds(song: SongTimeline, bpm: number): number {
  return songDurationSeconds(song, bpm) + CAPTURE_TAIL_S
}

/** Click times relative to t0 (negative: they all happen before the song starts). */
export function countInSchedule(bpm: number, beats = COUNT_IN_BEATS): number[] {
  return Array.from({ length: beats }, (_, i) => (i - beats) * beatSeconds(bpm))
}

/** Count-in beat number (1..4) at time t relative to t0, or null outside the count-in. */
export function countInBeatAt(
  bpm: number,
  t: number,
  beats = COUNT_IN_BEATS
): number | null {
  const beat = beatSeconds(bpm)
  const start = -beats * beat
  if (t < start || t >= 0) return null
  return Math.min(beats, Math.floor((t - start) / beat) + 1)
}

/** Contract index of the note sounding at t (seconds since t0), or null between/outside notes. */
export function currentNoteIndex(
  song: SongTimeline,
  bpm: number,
  t: number
): number | null {
  for (const note of song.notes) {
    const start = beatsToSeconds(note.start_beats, bpm)
    const end = beatsToSeconds(note.start_beats + note.duration_beats, bpm)
    if (t >= start && t < end) return note.index
  }
  return null
}

export function songProgressPct(song: SongTimeline, bpm: number, t: number): number {
  const duration = songDurationSeconds(song, bpm)
  if (!(duration > 0)) return 0
  return Math.max(0, Math.min(100, (t / duration) * 100))
}

export interface SongStripBar {
  /** 1-based bar number over the whole song. */
  bar: number
  notes: FluteSongNote[]
}

export interface SongStripPass {
  pass: FluteSongPass
  label: string
  bars: SongStripBar[]
}

export function passLabel(pass: FluteSongPass): string {
  return `${pass}ª vuelta`
}

/** S3: note strip grouped by pass (1ª/2ª vuelta) and by bar. */
export function groupSongStrip(
  song: Pick<FluteSong, "notes" | "beats_per_bar">
): SongStripPass[] {
  const beatsPerBar = song.beats_per_bar > 0 ? song.beats_per_bar : 4
  const passes: SongStripPass[] = []
  for (const note of song.notes) {
    let group = passes.find((p) => p.pass === note.pass)
    if (!group) {
      group = { pass: note.pass, label: passLabel(note.pass), bars: [] }
      passes.push(group)
    }
    const barNumber = Math.floor(note.start_beats / beatsPerBar) + 1
    let bar = group.bars.find((b) => b.bar === barNumber)
    if (!bar) {
      bar = { bar: barNumber, notes: [] }
      group.bars.push(bar)
    }
    bar.notes.push(note)
  }
  return passes
}

export function computeRms(waveform: Float32Array): number {
  if (waveform.length === 0) return 0
  let sumSq = 0
  for (let i = 0; i < waveform.length; i++) sumSq += waveform[i] * waveform[i]
  return Math.sqrt(sumSq / waveform.length)
}

/** Evenly downsample (order preserved) so the list never exceeds `max` items. */
export function capEvenly<T>(items: readonly T[], max: number): T[] {
  if (items.length <= max) return [...items]
  return Array.from(
    { length: max },
    (_, i) => items[Math.floor((i * items.length) / max)]
  )
}

export interface SongCaptureInput {
  song: Pick<FluteSong, "id" | "notes">
  tempoBpm: number
  pitchTrack: readonly FlutePitchSample[]
  audioFrames: readonly FluteTimedFeatures[]
  handFrames: readonly FluteTimedFeatures[]
}

export function clampSongTempo(bpm: number): number {
  return Math.max(SONG_MIN_BPM, Math.min(SONG_MAX_BPM, Math.round(bpm)))
}

/** Contract body for POST score-song; t is relative to t0 (end of the count-in). */
export function buildScoreSongPayload(input: SongCaptureInput): ScoreFluteSongPayload {
  const tempo = clampSongTempo(input.tempoBpm)
  const end = captureEndSeconds(input.song, tempo)
  const inRange = <T extends { t: number }>(items: readonly T[]) =>
    items.filter((s) => s.t >= -CAPTURE_PRE_ROLL_S && s.t <= end)
  return {
    song_id: input.song.id,
    tempo_bpm: tempo,
    pitch_track: capEvenly(inRange(input.pitchTrack), PITCH_TRACK_MAX),
    audio_schema: FLUTE_AUDIO_SCHEMA,
    audio_frames: capEvenly(inRange(input.audioFrames), AUDIO_FRAMES_MAX),
    visual_schema: FLUTE_VISUAL_SCHEMA,
    hand_frames: capEvenly(inRange(input.handFrames), HAND_FRAMES_MAX),
  }
}

/** S4: "+120 ms tarde" / "−80 ms adelantado" / "a tiempo". */
export function onsetLabel(onsetMs: number | null): string {
  if (onsetMs === null || !Number.isFinite(onsetMs)) return "sin entrada detectada"
  if (Math.abs(onsetMs) <= ON_TIME_TOLERANCE_MS) return "a tiempo"
  const ms = Math.round(Math.abs(onsetMs))
  return onsetMs > 0 ? `+${ms} ms tarde` : `−${ms} ms adelantado`
}

const NOTE_DISPLAY_NAMES: Record<string, string> = {
  DO: "Do",
  RE: "Re",
  MI: "Mi",
  FA: "Fa",
  "FA#": "Fa#",
  SOL: "Sol",
  LA: "La",
  SI: "Si",
  DO6: "Do agudo",
  RE6: "Re agudo",
  MI6: "Mi agudo",
}

export function noteDisplayName(note: string | null): string {
  if (note === null) return "—"
  return NOTE_DISPLAY_NAMES[note] ?? note
}

export function fingeringLabel(postureOk: boolean | null): string {
  if (postureOk === null) return "no evaluable"
  return postureOk ? "✓" : "✗"
}

export type NoteChipStatus = "pending" | "correct" | "wrong"

export function noteChipStatus(
  result: Pick<FluteSongNoteResult, "correct"> | undefined
): NoteChipStatus {
  if (!result) return "pending"
  return result.correct ? "correct" : "wrong"
}

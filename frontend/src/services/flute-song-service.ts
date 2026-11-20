import { apiClient } from "@/services/api-client"
import type { APIResponse } from "@/types/api"

/** Song pass: the score is played twice ("se hará dos veces"). */
export type FluteSongPass = 1 | 2

export interface FluteSongNote {
  index: number
  pass: FluteSongPass
  /** Backend note name (DO, RE, MI, FA, SOL…). */
  note: string
  start_beats: number
  duration_beats: number
}

export interface FluteSong {
  id: string
  title: string
  default_bpm: number
  min_bpm: number
  max_bpm: number
  beats_per_bar: number
  /** Public frontend path of the score image, e.g. "/flute-songs/himno_la_alegria.png". */
  image: string
  notes: FluteSongNote[]
}

export interface FlutePitchSample {
  /** Seconds since t0 (end of the count-in); may be negative down to -1.0 s. */
  t: number
  hz: number | null
  clarity: number
  rms: number
}

export interface FluteTimedFeatures {
  t: number
  features: number[]
}

export interface ScoreFluteSongPayload {
  song_id: string
  tempo_bpm: number
  pitch_track: FlutePitchSample[]
  audio_schema: "flute-audio-pitch-v1"
  audio_frames: FluteTimedFeatures[]
  visual_schema: "hand-landmarks-palm-v5"
  hand_frames: FluteTimedFeatures[]
}

export interface FluteSongNoteResult {
  index: number
  pass: FluteSongPass
  note: string
  expected_start_s: number
  duration_s: number
  detected_note: string | null
  pitch_share: number
  onset_ms: number | null
  timing_ok: boolean | null
  repeated: boolean
  articulation_ok: boolean | null
  flute_ok: boolean | null
  posture_ok: boolean | null
  posture_reason: string | null
  mismatched_holes: number[]
  correct: boolean
}

export interface FluteSongScore {
  song_id: string
  tempo_bpm: number
  model_version: string | null
  latency_offset_ms: number
  tuning_offset_cents: number
  notes: FluteSongNoteResult[]
  notes_correct: number
  notes_total: number
  sound_score: number
  posture_score: number | null
  total_score: number
  approved: boolean
  message: string
}

export function listFluteSongs(): Promise<APIResponse<FluteSong[]>> {
  return apiClient.get<FluteSong[]>("/ai/datasets/samples/flute/songs")
}

export function scoreFluteSong(
  payload: ScoreFluteSongPayload
): Promise<APIResponse<FluteSongScore>> {
  return apiClient.post<FluteSongScore>(
    "/ai/datasets/samples/flute/score-song",
    payload,
    { showToastOnError: false }
  )
}

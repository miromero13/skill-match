/**
 * Pure scoring/smoothing logic for the flute live validator (S7, S10) and
 * display helpers for the training studio (S2/S11). Kept free of React so it
 * can be unit-tested deterministically.
 */
import type {
  FluteFeatures,
  FluteFingerState,
  FluteInference,
  FluteModelVersionItem,
} from "@/services/dataset-sample-service"
import { FLUTE_AUDIO_SCHEMA, FLUTE_NOTES_MAP, type FluteNoteName } from "./flute-note-specs"
import { FLUTE_VISUAL_SCHEMA } from "./flute-hand-features"

/** Frames captured during the first 400 ms of a note (attack/transition) are ignored. */
export const ATTACK_IGNORE_MS = 400
/** Minimum voiced frames per segment for the sound to be scored at all. */
export const MIN_VOICED_FRAMES = 3
/** Minimum fraction of post-attack frames used as denominator for the sound score. */
export const MIN_VOICED_DENOMINATOR_RATIO = 0.4
export const NO_FLUTE_SOUND_REASON = "No se detectó sonido de flauta"
export const NO_FLUTE_CLASS = "NO_FLAUTA"
export const POSTURE_INCONCLUSIVE_REASON =
  "Digitación inconclusa: faltan observaciones fiables."
export const FREE_SMOOTHING_WINDOW = 3
export const BACK_THUMB_LABEL = "Pulgar trasero: no evaluable por cámara"
/** Index of the voiced flag inside the flute-audio-pitch-v1 vector. */
const AUDIO_VOICED_INDEX = 48

export type LiveFrame = Pick<
  FluteInference,
  | "voiced"
  | "sound_class"
  | "sound_ok"
  | "pitch_hz"
  | "pitch_cents_off"
  | "posture_ok"
  | "posture_reason"
  | "mismatched_holes"
>

export interface FreeFrame {
  voiced: boolean
  prediction: LiveFrame
}

export interface TimedFrame extends FreeFrame {
  /** Real elapsed time (performance.now()) since the segment started, in ms. */
  elapsedMs: number
}

export function isVoicedFrame(
  prediction: Pick<FluteInference, "voiced">,
  audioFeatures?: readonly number[]
): boolean {
  return prediction.voiced === true || audioFeatures?.[AUDIO_VOICED_INDEX] === 1
}

export function segmentProgressPct(startMs: number, nowMs: number, durationMs: number): number {
  if (durationMs <= 0) return 100
  const elapsed = Math.max(0, nowMs - startMs)
  return Math.min(100, Math.round((elapsed / durationMs) * 100))
}

export function isFluteNote(label: string | null | undefined): label is FluteNoteName {
  return label != null && Object.hasOwn(FLUTE_NOTES_MAP, label)
}

function mostFrequent(labels: readonly string[]): { label: string; count: number } | null {
  const votes = new Map<string, number>()
  let best: { label: string; count: number } | null = null
  for (const label of labels) {
    const count = (votes.get(label) ?? 0) + 1
    votes.set(label, count)
    if (!best || count > best.count) best = { label, count }
  }
  return best
}

function median(values: readonly number[]): number | null {
  if (values.length === 0) return null
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 1 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}

export interface ExamSegmentScore {
  postAttackFrames: number
  voicedFrames: number
  matchedFrames: number
  soundScorePct: number
  soundReason: string | null
  /** Most frequent sound_class among voiced post-attack frames, or NO_FLAUTA. */
  detectedNote: string
  postureOk: boolean | null
  postureReason: string | null
  /** Front holes mismatched in at least half of the evaluable post-attack frames. */
  mismatchedHoles: number[]
  segmentTotalPct: number | null
}

/**
 * S10 exam scoring for one note segment:
 * - frames before ATTACK_IGNORE_MS are discarded;
 * - sound = matches / max(voiced, ceil(0.4 · postAttack)); < 3 voiced → 0;
 * - posture = null if < 3 evaluable or < 70% evaluable, else ≥ 50% posture_ok;
 * - total = 75% sound + 25% posture, sound 0 → 0, posture null → null.
 */
export function scoreExamSegment(frames: readonly TimedFrame[]): ExamSegmentScore {
  const scored = frames.filter((f) => f.elapsedMs >= ATTACK_IGNORE_MS)
  const voiced = scored.filter((f) => f.voiced)
  const matched = voiced.filter((f) => f.prediction.sound_ok)

  let soundScorePct = 0
  let soundReason: string | null = null
  let detectedNote = NO_FLUTE_CLASS
  if (voiced.length < MIN_VOICED_FRAMES) {
    soundReason = NO_FLUTE_SOUND_REASON
  } else {
    const denominator = Math.max(
      voiced.length,
      Math.ceil(MIN_VOICED_DENOMINATOR_RATIO * scored.length)
    )
    soundScorePct = Math.round((100 * matched.length) / denominator)
    detectedNote = mostFrequent(voiced.map((f) => f.prediction.sound_class))?.label ?? NO_FLUTE_CLASS
  }

  const evaluable = scored.filter((f) => f.prediction.posture_ok !== null)
  let postureOk: boolean | null
  let postureReason: string | null = null
  if (evaluable.length < 3 || evaluable.length / Math.max(1, scored.length) < 0.7) {
    postureOk = null
    postureReason =
      scored.find((f) => f.prediction.posture_reason)?.prediction.posture_reason ??
      POSTURE_INCONCLUSIVE_REASON
  } else {
    postureOk =
      evaluable.filter((f) => f.prediction.posture_ok === true).length / evaluable.length >= 0.5
  }

  const holeMisses = new Map<number, number>()
  for (const f of evaluable) {
    for (const hole of f.prediction.mismatched_holes ?? []) {
      holeMisses.set(hole, (holeMisses.get(hole) ?? 0) + 1)
    }
  }
  const mismatchedHoles = [...holeMisses]
    .filter(([, misses]) => misses * 2 >= evaluable.length)
    .map(([hole]) => hole)
    .sort((a, b) => a - b)

  const segmentTotalPct =
    postureOk === null
      ? null
      : soundScorePct === 0
      ? 0
      : Math.round(soundScorePct * 0.75 + (postureOk ? 25 : 0))

  return {
    postAttackFrames: scored.length,
    voicedFrames: voiced.length,
    matchedFrames: matched.length,
    soundScorePct,
    soundReason,
    detectedNote,
    postureOk,
    postureReason,
    mismatchedHoles,
    segmentTotalPct,
  }
}

export function pushFreeWindow(window: readonly FreeFrame[], next: FreeFrame): FreeFrame[] {
  return [...window, next].slice(-FREE_SMOOTHING_WINDOW)
}

export interface FreeSmoothedState {
  /** Note heard in the majority (≥ 2) of the voiced frames of the window. */
  note: FluteNoteName | null
  /** Median pitch of the voiced frames of the window. */
  pitchHz: number | null
  /** Median cents offset of the voiced frames that agree with `note`. */
  centsOff: number | null
  /** Majority of the evaluable (posture_ok !== null) frames; null with < 2 evaluable. */
  postureOk: boolean | null
  /** Set only when smoothed sound and smoothed posture agree. */
  confirmedNote: FluteNoteName | null
}

/** S10 free mode: same backend posture_ok as exam mode, smoothed over the last 3 frames. */
export function smoothFreeWindow(window: readonly FreeFrame[]): FreeSmoothedState {
  const recent = window.slice(-FREE_SMOOTHING_WINDOW)
  const voiced = recent.filter((f) => f.voiced)
  const winner = mostFrequent(voiced.map((f) => f.prediction.sound_class))
  const note = winner && winner.count >= 2 && isFluteNote(winner.label) ? winner.label : null

  const pitchHz = median(
    voiced.flatMap((f) => (f.prediction.pitch_hz == null ? [] : [f.prediction.pitch_hz]))
  )
  const centsOff =
    note === null
      ? null
      : median(
          voiced.flatMap((f) =>
            f.prediction.sound_class === note && f.prediction.pitch_cents_off != null
              ? [f.prediction.pitch_cents_off]
              : []
          )
        )

  const evaluable = recent.filter((f) => f.prediction.posture_ok !== null)
  const okCount = evaluable.filter((f) => f.prediction.posture_ok === true).length
  const postureOk = evaluable.length < 2 ? null : okCount * 2 > evaluable.length

  return {
    note,
    pitchHz,
    centsOff,
    postureOk,
    confirmedNote: note !== null && postureOk === true ? note : null,
  }
}

export interface FingerHoleView {
  hole: number
  hand: "left" | "right"
  expected: boolean | null
  covered: boolean
  coveredProbability: number
  /** null when there is no note to compare or the hole is uncertain. */
  match: boolean | null
  /** Camera cannot tell covered/uncovered (backend `uncertain_holes`); neutral, not an error. */
  uncertain: boolean
  /** Mismatch (error) or uncertain (neutral) explanation; null otherwise. */
  message: string | null
}

export function UNCERTAIN_HOLE_MESSAGE(hole: number): string {
  return `Hueco ${hole}: la cámara no lo ve con claridad`
}

export function fingerMismatchMessage(hole: number, expectedCovered: boolean): string {
  return `Hueco ${hole} debería estar ${expectedCovered ? "tapado" : "destapado"}`
}

/**
 * S7: always 7 front holes (1-3 left hand, 4-7 right hand); the back thumb is not evaluable.
 * Uncertain holes (covered probability near 0.5) are shown as a neutral camera notice.
 */
export function describeFingerStates(
  states: readonly FluteFingerState[] | null,
  uncertainHoles: readonly number[] = []
): FingerHoleView[] {
  return [1, 2, 3, 4, 5, 6, 7].map((hole) => {
    const state = states?.find((s) => s.hole === hole)
    const coveredProbability = state?.covered_probability ?? 0
    const expected = state?.expected ?? null
    const uncertain = uncertainHoles.includes(hole)
    const match = uncertain ? null : state?.match ?? null
    return {
      hole,
      hand: hole <= 3 ? "left" : "right",
      expected,
      covered: state != null && coveredProbability >= 0.5,
      coveredProbability,
      match,
      uncertain,
      message: uncertain
        ? UNCERTAIN_HOLE_MESSAGE(hole)
        : match === false && expected !== null
        ? fingerMismatchMessage(hole, expected)
        : null,
    }
  })
}

export function buildFluteInferPayload(
  audioFeatures: number[],
  visualFeatures: number[],
  targetNote: string | null
): FluteFeatures & { target_note: string | null } {
  return {
    target_note: targetNote,
    audio_features: audioFeatures,
    audio_schema: FLUTE_AUDIO_SCHEMA,
    visual_features: visualFeatures,
    visual_schema: FLUTE_VISUAL_SCHEMA,
  }
}

type FluteMetrics = FluteModelVersionItem["metricas"]

export function fluteSplitModeLabel(mode: FluteMetrics["split_mode"]): string {
  switch (mode) {
    case "participant":
      return "Validado con personas independientes"
    case "session":
      return "Intra-persona, otra sesión"
    case "take":
      return "Intra-persona, otras tomas (optimista)"
    default:
      return "Sin partición de prueba"
  }
}

export function isLegacyFluteModel(
  metricas: Pick<FluteMetrics, "audio_schema" | "visual_schema">
): boolean {
  return metricas.audio_schema !== FLUTE_AUDIO_SCHEMA || metricas.visual_schema !== FLUTE_VISUAL_SCHEMA
}

import type { FluteFeatures, FluteLabels, FlutePreviewSample } from "@/services/dataset-sample-service"
import {
  FLUTE_AUDIO_SCHEMA, FLUTE_NOTES_MAP, computePitchAgreement, gateFluteFrames, isVoicedAudioFrame,
  pitchAgreementRejection, type FluteNoteName,
} from "./flute-note-specs"
import { FLUTE_VISUAL_SCHEMA, countDetectedHands } from "./flute-hand-features"

/** Shared logic for re-extracting features from stored MP4 takes (single video and batch). */

export const REPROCESS_UNKNOWN_DURATION_TIMEOUT_MS = 30_000
export const REPROCESS_TIMEOUT_MARGIN_MS = 10_000
export const REPROCESS_STOPPED_REASON = "Reprocesamiento detenido."
export const LABELS_KEPT_SUFFIX = "No se modificaron las etiquetas anteriores."

export type ReprocessOutcome = { ok: true } | { ok: false; reason: string }

export interface ReprocessItemControls {
  /** Replaces the item deadline (counted from now), e.g. once the video duration is known. */
  setDeadline: (ms: number) => void
  /**
   * Call right before sending the save request. From then on Detener and the deadline no longer
   * cut the item: the request cannot be recalled, so the queue waits for its real outcome.
   */
  markSaving: () => void
}

export type ProcessOne = (
  sample: FlutePreviewSample,
  signal: AbortSignal,
  controls: ReprocessItemControls
) => Promise<ReprocessOutcome>

export interface ReprocessProgress {
  /** 1-based position of the item being processed. */
  index: number
  total: number
  sample: FlutePreviewSample
}

export interface ReprocessFailure {
  id: string
  shortId: string
  note: string
  participant: string
  reason: string
}

export interface ReprocessQueueSummary {
  total: number
  okCount: number
  failures: ReprocessFailure[]
  /** True when the admin pressed Detener (the cancelled item is not saved nor listed as failure). */
  stopped: boolean
  /** Items never completed: the cancelled one plus the remaining ones. */
  notProcessed: number
}

export interface PitchCheckSummary {
  agreement: number
  voicedFrames: number
  rejected: boolean
}

export type ReprocessTakeResult =
  | { ok: true; message: string; pitch: PitchCheckSummary | null }
  | { ok: false; kind: "rejected" | "error" | "cancelled"; reason: string; pitch: PitchCheckSummary | null }

export type SaveFluteLabels = (sampleId: string, payload: FluteLabels) => Promise<{ message: string }>

type ReviewedSample = FlutePreviewSample & {
  participant_id: string
  sound_label: FluteLabels["sound_label"]
  posture_label: FluteLabels["posture_label"]
}

function hasReviewedLabels(sample: FlutePreviewSample): sample is ReviewedSample {
  return Boolean(sample.participant_id && sample.sound_label && sample.posture_label)
}

/** Stored MP4 takes in an older feature format that keep reviewed labels (batch candidates). */
export function selectPendingReprocessSamples(samples: readonly FlutePreviewSample[]): FlutePreviewSample[] {
  return samples.filter(s => s.file_format === "mp4" && s.needs_reprocess && hasReviewedLabels(s))
}

function noteOrSound(sample: FlutePreviewSample): string {
  return sample.note_label ?? sample.sound_label ?? "—"
}

export function describeReprocessProgress({ index, total, sample }: ReprocessProgress): string {
  return `Procesando ${index} de ${total} · ${noteOrSound(sample)} · participante ${sample.participant_id ?? "—"}`
}

/** Per-item safeguard: video duration + 10 s, or 30 s when the duration is unknown. */
export function reprocessItemTimeoutMs(durationSeconds: number): number {
  return Number.isFinite(durationSeconds) && durationSeconds > 0
    ? Math.round(durationSeconds * 1000) + REPROCESS_TIMEOUT_MARGIN_MS
    : REPROCESS_UNKNOWN_DURATION_TIMEOUT_MS
}

export function labeledFluteNote(sample: FlutePreviewSample): FluteNoteName | null {
  return sample.note_label && Object.hasOwn(FLUTE_NOTES_MAP, sample.note_label)
    ? sample.note_label as FluteNoteName : null
}

/**
 * One frame of the stored video, or null when it must be skipped: no fresh hand frame,
 * correct-posture takes missing the note's required hands, or silent audio on flute takes.
 * Audio is only read once the hand gates pass.
 */
export function collectReprocessFrame(
  sample: FlutePreviewSample,
  handFeatures: number[] | null,
  readAudio: () => number[]
): FluteFeatures | null {
  if (!handFeatures) return null
  const note = labeledFluteNote(sample)
  const required = note ? FLUTE_NOTES_MAP[note].handsRequired : 1
  if (sample.posture_label === "correcta" && countDetectedHands(handFeatures) < required) return null
  const audioFeatures = readAudio()
  // Silence gating: flute takes keep only voiced frames; voz/ruido negatives keep all.
  if (sample.sound_label === "flauta" && !isVoicedAudioFrame(audioFeatures)) return null
  return { visual_schema: FLUTE_VISUAL_SCHEMA, visual_features: handFeatures,
    audio_schema: FLUTE_AUDIO_SCHEMA, audio_features: audioFeatures }
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback
}

/**
 * Gates the recorded frames (silence + pitch agreement + minimum frames) and saves them keeping
 * the sample's labels. Rejected or stopped takes are never saved, so they keep their previous labels.
 */
export async function finalizeReprocessTake(
  sample: FlutePreviewSample,
  rawFrames: readonly FluteFeatures[],
  save: SaveFluteLabels,
  signal?: AbortSignal,
  onSaveStart?: () => void
): Promise<ReprocessTakeResult> {
  if (!hasReviewedLabels(sample)) return { ok: false, kind: "rejected", reason: "Faltan etiquetas revisadas.", pitch: null }
  const isFluteTake = sample.sound_label === "flauta"
  const note = labeledFluteNote(sample)
  const frames = gateFluteFrames(rawFrames, sample.sound_label)
  let pitch: PitchCheckSummary | null = null
  if (isFluteTake && note) {
    const agreement = computePitchAgreement(frames.map(frame => frame.audio_features), note)
    const rejection = pitchAgreementRejection(agreement, note)
    pitch = { agreement: agreement.agreement, voicedFrames: agreement.voicedFrames, rejected: rejection !== null }
    if (rejection) return { ok: false, kind: "rejected", reason: rejection, pitch }
  }
  if (frames.length < 3) {
    return { ok: false, kind: "rejected", pitch, reason: isFluteTake
      ? "No se detectaron suficientes fotogramas con manos y sonido."
      : "No se detectaron suficientes articulaciones." }
  }
  if (signal?.aborted) return { ok: false, kind: "cancelled", reason: REPROCESS_STOPPED_REASON, pitch }
  onSaveStart?.()
  try {
    const response = await save(sample.id, { ...frames[Math.floor(frames.length / 2)],
      feature_frames: frames, participant_id: sample.participant_id, note_label: sample.note_label,
      sound_label: sample.sound_label, posture_label: sample.posture_label })
    return { ok: true, message: response.message, pitch }
  } catch (error: unknown) {
    return { ok: false, kind: "error", reason: errorMessage(error, "No se pudo reprocesar."), pitch }
  }
}

type ItemEnd = { kind: "done"; outcome: ReprocessOutcome } | { kind: "stopped" } | { kind: "timeout"; ms: number }

async function runItem(
  sample: FlutePreviewSample,
  processOne: ProcessOne,
  signal: AbortSignal
): Promise<ItemEnd> {
  const item = new AbortController()
  let timer: ReturnType<typeof setTimeout> | undefined
  let settle: (end: ItemEnd) => void = () => undefined
  const ended = new Promise<ItemEnd>(resolve => { settle = resolve })
  let saving = false
  const setDeadline = (ms: number) => {
    if (saving) return
    clearTimeout(timer)
    timer = setTimeout(() => { settle({ kind: "timeout", ms }); item.abort() }, ms)
  }
  const markSaving = () => { saving = true; clearTimeout(timer) }
  // Once the save request is in flight it cannot be recalled: wait for its real outcome.
  const onStop = () => { if (!saving) { settle({ kind: "stopped" }); item.abort() } }
  signal.addEventListener("abort", onStop)
  setDeadline(REPROCESS_UNKNOWN_DURATION_TIMEOUT_MS)
  Promise.resolve()
    .then(() => processOne(sample, item.signal, { setDeadline, markSaving }))
    .then(
      outcome => settle({ kind: "done", outcome }),
      (error: unknown) => settle({ kind: "done", outcome: { ok: false, reason: errorMessage(error, "No se pudo reprocesar.") } })
    )
  try {
    return await ended
  } finally {
    clearTimeout(timer)
    signal.removeEventListener("abort", onStop)
  }
}

/**
 * Processes the snapshot of samples one by one. A failing item does not stop the queue; aborting
 * `signal` cancels the current item (unsaved) and skips the rest. `onSaved` runs exactly once at the end.
 */
export async function runReprocessQueue({ samples, processOne, signal, onProgress, onSaved }: {
  samples: readonly FlutePreviewSample[]
  processOne: ProcessOne
  signal: AbortSignal
  onProgress?: (progress: ReprocessProgress) => void
  onSaved: () => Promise<void>
}): Promise<ReprocessQueueSummary> {
  const queue = [...samples]
  const failures: ReprocessFailure[] = []
  let okCount = 0
  for (const [i, sample] of queue.entries()) {
    if (signal.aborted) break
    onProgress?.({ index: i + 1, total: queue.length, sample })
    const end = await runItem(sample, processOne, signal)
    if (end.kind === "stopped") break
    const outcome: ReprocessOutcome = end.kind === "timeout"
      ? { ok: false, reason: `Tiempo de espera agotado (${Math.round(end.ms / 1000)} s). ${LABELS_KEPT_SUFFIX}` }
      : end.outcome
    if (outcome.ok) okCount += 1
    else failures.push({ id: sample.id, shortId: sample.id.slice(0, 8), note: noteOrSound(sample),
      participant: sample.participant_id ?? "—", reason: outcome.reason })
    if (signal.aborted) break // Detener arrived while this item's save was in flight.
  }
  try { await onSaved() } catch { /* the refresh failure is surfaced by the API client toast */ }
  return { total: queue.length, okCount, failures, stopped: signal.aborted,
    notProcessed: queue.length - okCount - failures.length }
}

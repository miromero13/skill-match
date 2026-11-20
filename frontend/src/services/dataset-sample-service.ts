
import { apiClient } from "@/services/api-client"
import type {
  DatasetSample,
  DatasetSampleContent,
  DatasetSampleUploadPayload,
} from "@/types/dataset-sample"
import type { APIResponse } from "@/types/api"

export interface FluteFeatures {
  /** 62 floats, layout documented in flute-note-specs.ts (flute-audio-pitch-v1). */
  audio_features: number[]
  audio_schema: "flute-audio-pitch-v1"
  /** 50 floats (25 per hand slot, slot 0 = user's left hand). */
  visual_features: number[]
  visual_schema: "hand-landmarks-palm-v5"
}

export interface FluteLabels extends FluteFeatures {
  feature_frames: FluteFeatures[]
  participant_id: string
  note_label: string | null
  sound_label: "flauta" | "voz" | "ruido"
  posture_label: "correcta" | "incorrecta" | "sin_manos"
}

export interface FluteClassProbability {
  label: string
  probability: number
}

/** State of one front hole (1-3 left hand, 4-7 right hand) seen by the camera. */
export interface FluteFingerState {
  hole: number
  /** Expected state for the evaluated note (true = covered), null when no note is evaluated. */
  expected: boolean | null
  covered_probability: number
  /** null when no note is evaluated or the camera is unsure (probability in 0.35..0.65). */
  match: boolean | null
}

export interface FluteInference {
  model_id: string
  model_version: string
  validated: boolean
  experimental?: boolean
  target_note: string | null
  /** Pitch-first decision: detected note, or NO_FLAUTA when silent/not flute/out of tune. */
  sound_class: string
  sound_confidence: number
  sound_ok: boolean
  top_sound_classes?: FluteClassProbability[]
  voiced: boolean
  pitch_hz: number | null
  pitch_note: string | null
  pitch_cents_off: number | null
  /** Probability (0..1) that the frame sounds like a flute (MLP head). */
  flute_probability: number
  posture_ok: boolean | null
  posture_evaluable: boolean
  posture_reason: string | null
  finger_states: FluteFingerState[] | null
  finger_match_ratio: number | null
  /** Holes the camera confidently sees in the wrong state (any one fails the posture). */
  mismatched_holes: number[]
  /** Holes the camera cannot see clearly (at most one is tolerated). */
  uncertain_holes: number[]
  combined_note?: string | null
  combined_match?: boolean
}

export interface FluteClassReport {
  precision: number | null
  recall: number | null
  support: number
}

interface FluteHeadMetrics {
  train_accuracy?: number | null
  /** Frame-level accuracy on the held-out split. */
  test_accuracy: number | null
  /** Take-level accuracy (frames of one video aggregated) on the held-out split. */
  sample_test_accuracy?: number | null
  majority_baseline_accuracy?: number | null
  classes: string[]
  /** Take-level confusion matrix [true][pred] on the held-out split. */
  confusion_matrix: number[][]
  per_class?: Record<string, FluteClassReport>
  per_participant?: Record<string, number | null>
  train_class_counts: Record<string, number>
  loss_history: Array<{ epoch: number; loss: number }>
}

interface FluteFingerMetrics {
  holes: number[]
  /** Mean per-hole accuracy (frames). */
  train_accuracy: number | null
  test_accuracy: number | null
  majority_baseline_accuracy: number | null
  /** Fraction of held-out takes whose fingering was fully recognised. */
  sample_test_accuracy: number | null
  per_hole: Array<{ hole: number; test_accuracy: number | null; baseline: number | null }>
  train_frames: number
  loss_history: Array<{ epoch: number; loss: number }>
}

export interface FluteModelVersionItem {
  id: string
  version: string
  activa: boolean
  metricas: {
    validated: boolean
    validation_note: string
    /** participant = independent people; session = same person, other day; take = same session. */
    split_mode?: "participant" | "session" | "take" | "none"
    labeled_samples: number
    train_samples: number
    test_samples: number
    sound: FluteHeadMetrics
    fingers?: FluteFingerMetrics
    tuning_offset_cents?: number
    latency_ms_per_inference: number
    visual_schema?: string
    audio_schema?: string
    metric_unit?: string
  }
}

export interface FlutePreviewSample {
  id: string
  labeled: boolean
  participant_id: string | null
  note_label: string | null
  sound_label: FluteLabels["sound_label"] | null
  posture_label: FluteLabels["posture_label"] | null
  /** True when a sidecar exists in an older feature format: reprocess the stored video. */
  needs_reprocess: boolean
  /** Fraction of voiced frames whose pitch matched the labeled note (flute takes only). */
  pitch_agreement: number | null
  file_format: string
}

export interface FluteDatasetPreviewResponse {
  samples: FlutePreviewSample[]
  feature_frames_count: number
  total_count: number
  labeled_count: number
  unlabeled_count: number
  needs_reprocess_count: number
  participants: Record<string, number>
  sessions_count: number
  sound_class_counts: Record<string, number>
  /** Frames with reviewed correct fingering per note (finger head training data). */
  finger_note_counts: Record<string, number>
  can_validate_independently: boolean
}

export function saveFluteLabels(sampleId: string, payload: FluteLabels) {
  return apiClient.post<
    Pick<
      FluteLabels,
      "participant_id" | "note_label" | "sound_label" | "posture_label"
    >
  >(
    `/ai/datasets/samples/${sampleId}/flute-labels`,
    payload,
    { showToastOnSuccess: true }
  )
}

export function inferFlute(payload: FluteFeatures & { target_note?: string | null }) {
  return apiClient.post<FluteInference>(
    "/ai/datasets/samples/flute/infer",
    payload
  )
}

export async function calculateFileSha256(blob: Blob): Promise<string> {
  const arrayBuffer = await blob.arrayBuffer()
  const hashBuffer = await crypto.subtle.digest("SHA-256", arrayBuffer)
  const hashArray = Array.from(new Uint8Array(hashBuffer))
  return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("")
}

export async function getDatasetSamples(
  page = 1,
  pageSize = 50,
  discipline?: string
): Promise<APIResponse<DatasetSample[]>> {
  return apiClient.get<DatasetSample[]>("/ai/datasets/samples", {
    params: {
      page,
      page_size: pageSize,
      discipline: discipline || undefined,
    },
  })
}

export async function uploadDatasetSample(
  payload: DatasetSampleUploadPayload
): Promise<APIResponse<DatasetSample>> {
  const formData = new FormData()

  const fileToUpload =
    payload.file instanceof File
      ? payload.file
      : new File([payload.file], payload.fileName, {
        type: payload.file.type,
      })

  formData.append("file", fileToUpload)
  formData.append("discipline", payload.discipline)
  formData.append("challenge", payload.challenge)
  formData.append("hardware_info", payload.hardware_info)
  formData.append("signed_consent", String(payload.signed_consent))

  if (payload.file_hash_sha256) {
    formData.append("file_hash_sha256", payload.file_hash_sha256)
  }

  if (payload.participant_id) {
    formData.append("participant_id", payload.participant_id)
  }

  if (payload.level_label) {
    formData.append("level_label", payload.level_label)
  }

  if (
    payload.manual_touch_count !== undefined &&
    payload.manual_touch_count !== null
  ) {
    formData.append(
      "manual_touch_count",
      String(payload.manual_touch_count)
    )
  }

  if (payload.noise_level) {
    formData.append("noise_level", payload.noise_level)
  }

  if (payload.surface) {
    formData.append("surface", payload.surface)
  }

  if (payload.split) {
    formData.append("split", payload.split)
  }

  return apiClient.post<DatasetSample>(
    "/ai/datasets/samples/upload",
    formData,
    { showToastOnSuccess: true }
  )
}

export async function deleteDatasetSample(
  id: string
): Promise<APIResponse<null>> {
  return apiClient.delete<null>(
    `/ai/datasets/samples/${id}`,
    { showToastOnSuccess: true }
  )
}

export async function getDatasetSampleContent(
  id: string
): Promise<APIResponse<DatasetSampleContent>> {
  return apiClient.get<DatasetSampleContent>(
    `/ai/datasets/samples/${id}/content`
  )
}

export async function getFluteDatasetPreview(): Promise<
  APIResponse<FluteDatasetPreviewResponse>
> {
  return apiClient.get<FluteDatasetPreviewResponse>(
    "/ai/datasets/samples/flute/preview"
  )
}

export async function trainFluteModel(payload: {
  version_tag?: string
  activate?: boolean
  skill_id?: string
}): Promise<APIResponse<FluteModelVersionItem>> {
  return apiClient.post<FluteModelVersionItem>(
    "/ai/datasets/samples/flute/train",
    payload,
    { showToastOnSuccess: true }
  )
}

export async function listFluteModels(): Promise<
  APIResponse<FluteModelVersionItem[]>
> {
  return apiClient.get<FluteModelVersionItem[]>(
    "/ai/datasets/samples/flute/models"
  )
}

export async function activateFluteModel(
  modelId: string
): Promise<APIResponse<FluteModelVersionItem>> {
  return apiClient.post<FluteModelVersionItem>(
    `/ai/datasets/samples/flute/models/${modelId}/activate`,
    {},
    { showToastOnSuccess: true }
  )
}

export async function getDatasetSamplePreviewUrl(
  id: string
): Promise<
  APIResponse<{ preview_url: string; file_format: string }>
> {
  return apiClient.get<{
    preview_url: string
    file_format: string
  }>(
    `/ai/datasets/samples/${id}/preview-url`,
    { showToastOnError: false }
  )
}

import { apiClient } from "@/services/api-client"
import type {
  DatasetSample,
  DatasetSampleContent,
  DatasetSampleUploadPayload,
} from "@/types/dataset-sample"
import type { APIResponse } from "@/types/api"

export interface FluteFeatures {
  audio_features: number[]
  visual_features: number[]
  visual_schema: "hand-landmarks-palm-v2"
}

export interface FluteLabels extends FluteFeatures {
  feature_frames: FluteFeatures[]
  participant_id: string
  note_label: string | null
  sound_label: "flauta" | "voz" | "ruido"
  posture_label: "correcta" | "incorrecta" | "sin_manos"
}

export interface FluteInference {
  model_id: string
  model_version: string
  validated: boolean
  target_note: string
  sound_class: string
  sound_confidence: number
  sound_ok: boolean
  posture_class: string
  posture_confidence: number
  posture_ok: boolean | null
  posture_evaluable: boolean
  posture_reason: string | null
}

interface FluteHeadMetrics {
  test_accuracy: number | null
  rule_baseline_accuracy?: number | null
  majority_baseline_accuracy?: number | null
  classes: string[]
  confusion_matrix: number[][]
  train_class_counts: Record<string, number>
  loss_history: Array<{ epoch: number; loss: number }>
}

export interface FluteModelVersionItem {
  id: string
  version: string
  activa: boolean
  metricas: {
    validated: boolean
    validation_note: string
    labeled_samples: number
    train_samples: number
    test_samples: number
    sound: FluteHeadMetrics
    posture: FluteHeadMetrics
    latency_ms_per_inference: number
    visual_schema?: string
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
  file_format: string
}

export interface FluteDatasetPreviewResponse {
  samples: FlutePreviewSample[]
  feature_frames_count: number
  total_count: number
  labeled_count: number
  unlabeled_count: number
  participants: Record<string, number>
  sound_class_counts: Record<string, number>
  posture_class_counts: Record<string, number>
  can_validate_independently: boolean
}

export function saveFluteLabels(sampleId: string, payload: FluteLabels) {
  return apiClient.post<Pick<FluteLabels, "participant_id" | "note_label" | "sound_label" | "posture_label">>(
    `/ai/datasets/samples/${sampleId}/flute-labels`, payload, { showToastOnSuccess: true }
  )
}

export function inferFlute(payload: FluteFeatures & { target_note: string }) {
  return apiClient.post<FluteInference>("/ai/datasets/samples/flute/infer", payload)
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
      : new File([payload.file], payload.fileName, { type: payload.file.type })

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
    formData.append("manual_touch_count", String(payload.manual_touch_count))
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

  return apiClient.post<DatasetSample>("/ai/datasets/samples/upload", formData, {
    showToastOnSuccess: true,
  })
}

export async function deleteDatasetSample(
  id: string
): Promise<APIResponse<null>> {
  return apiClient.delete<null>(`/ai/datasets/samples/${id}`, {
    showToastOnSuccess: true,
  })
}

export async function getDatasetSampleContent(
  id: string
): Promise<APIResponse<DatasetSampleContent>> {
  return apiClient.get<DatasetSampleContent>(`/ai/datasets/samples/${id}/content`)
}

export async function getFluteDatasetPreview(): Promise<
  APIResponse<FluteDatasetPreviewResponse>
> {
  return apiClient.get<FluteDatasetPreviewResponse>("/ai/datasets/samples/flute/preview")
}

export async function trainFluteModel(payload: {
  version_tag?: string
  activate?: boolean
  skill_id?: string
}): Promise<APIResponse<FluteModelVersionItem>> {
  return apiClient.post<FluteModelVersionItem>("/ai/datasets/samples/flute/train", payload, {
    showToastOnSuccess: true,
  })
}

export async function listFluteModels(): Promise<
  APIResponse<FluteModelVersionItem[]>
> {
  return apiClient.get<FluteModelVersionItem[]>("/ai/datasets/samples/flute/models")
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

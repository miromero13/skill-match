import { apiClient } from "@/services/api-client"
import type { DatasetSample, DatasetSampleUploadPayload } from "@/types/dataset-sample"
import type { APIResponse } from "@/types/api"

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

export async function getDatasetSamplePreviewUrl(
  id: string
): Promise<APIResponse<{ preview_url: string; file_format: string }>> {
  return apiClient.get<{ preview_url: string; file_format: string }>(
    `/ai/datasets/samples/${id}/preview-url`,
    { showToastOnError: false }
  )
}

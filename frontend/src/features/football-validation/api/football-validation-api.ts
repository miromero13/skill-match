import { apiClient } from "@/services/api-client"
import type { APIResponse } from "@/types/api"
import type {
  CalibrationPayload,
  CalibrationResponse,
  ChunkUploadResponse,
  CreateValidationSessionResponse,
  EnvCheckPayload,
  EnvCheckResponse,
  FinalizeSessionPayload,
  FinalizeSessionResponse,
  LivenessPayload,
  LivenessResponse,
  ValidationResultPayload,
  ValidationSessionStatusResponse,
} from "../state/football-session-machine"

export async function computeBlobSha256Hex(blob: Blob): Promise<string> {
  const buffer = await blob.arrayBuffer()
  if (typeof crypto !== "undefined" && crypto.subtle) {
    const digest = await crypto.subtle.digest("SHA-256", buffer)
    const byteArray = Array.from(new Uint8Array(digest))
    return byteArray.map((b) => b.toString(16).padStart(2, "0")).join("")
  }
  return ""
}

export interface TrainedModelMetrics {
  test_samples: number
  train_participants: number
  test_participants: number
  rule_baseline_accuracy: number
  trained_exact_accuracy: number
  trained_within_one_level_accuracy: number
  beats_rule_baseline: boolean
  confusion_matrix: number[][]
  loss_history: Array<{ epoch: number; loss: number }>
  dataset_source?: string
  real_samples_count?: number
  synthetic_samples_count?: number
  total_samples_count?: number
  latency_ms_per_inference?: number
  touch_mae?: number
  skill_id?: string | null
}

export interface TrainedModelVersion {
  id: string
  nombre: string
  version: string
  ruta_onnx: string
  activa: boolean
  metricas: TrainedModelMetrics
  created_at: string
}

export interface TrainingStatus {
  status: "queued" | "running" | "done" | "failed"
  processed: number | null
  total: number | null
  message: string | null
  result: TrainedModelVersion | null
}

export const footballValidationApi = {
  async createSession(
    skillId?: string
  ): Promise<APIResponse<CreateValidationSessionResponse>> {
    return apiClient.post<CreateValidationSessionResponse>(
      "/football/sessions",
      skillId ? { skill_id: skillId } : {}
    )
  },

  async getSessionStatus(
    sessionId: string
  ): Promise<APIResponse<ValidationSessionStatusResponse>> {
    return apiClient.get<ValidationSessionStatusResponse>(
      `/football/sessions/${sessionId}`,
      { showToastOnError: false }
    )
  },

  async submitEnvCheck(
    sessionId: string,
    payload: EnvCheckPayload
  ): Promise<APIResponse<EnvCheckResponse>> {
    return apiClient.post<EnvCheckResponse>(
      `/football/sessions/${sessionId}/env-check`,
      payload
    )
  },

  async submitLiveness(
    sessionId: string,
    payload: LivenessPayload
  ): Promise<APIResponse<LivenessResponse>> {
    return apiClient.post<LivenessResponse>(
      `/football/sessions/${sessionId}/liveness`,
      payload
    )
  },

  async submitCalibration(
    sessionId: string,
    payload: CalibrationPayload
  ): Promise<APIResponse<CalibrationResponse>> {
    return apiClient.post<CalibrationResponse>(
      `/football/sessions/${sessionId}/calibration`,
      payload
    )
  },

  async uploadChunk(
    sessionId: string,
    chunkIndex: number,
    chunkBlob: Blob,
    sha256Hex?: string
  ): Promise<APIResponse<ChunkUploadResponse>> {
    const formData = new FormData()
    const ext = chunkBlob.type.includes("webm") ? "webm" : "mp4"
    formData.append("file", chunkBlob, `chunk-${chunkIndex}.${ext}`)

    const headers: Record<string, string> = {}
    if (sha256Hex) {
      headers["X-Chunk-Sha256"] = sha256Hex
    }

    return apiClient.put<ChunkUploadResponse>(
      `/football/sessions/${sessionId}/chunks/${chunkIndex}`,
      formData,
      {
        headers,
        showToastOnError: false,
      }
    )
  },

  async finalizeSession(
    sessionId: string,
    payload?: FinalizeSessionPayload
  ): Promise<APIResponse<FinalizeSessionResponse>> {
    return apiClient.post<FinalizeSessionResponse>(
      `/football/sessions/${sessionId}/finalize`,
      payload ?? {},
      { showToastOnSuccess: true }
    )
  },

  async getSessionResult(
    sessionId: string
  ): Promise<APIResponse<ValidationResultPayload>> {
    return apiClient.get<ValidationResultPayload>(
      `/football/sessions/${sessionId}/result`
    )
  },

  async enqueueTraining(payload: {
    version_tag?: string
    activate?: boolean
    dataset_source?: "all" | "custom_ids"
    sample_ids?: string[]
    skill_id?: string
  }): Promise<APIResponse<{ task_id: string }>> {
    return apiClient.post("/football/training/train", payload)
  },

  async getTrainingStatus(taskId: string): Promise<APIResponse<TrainingStatus>> {
    return apiClient.get(`/football/training/train/${taskId}/status`, {
      showToastOnError: false,
    })
  },

  async listModelVersions(): Promise<APIResponse<TrainedModelVersion[]>> {
    return apiClient.get("/football/training/models")
  },

  async activateModelVersion(
    modelId: string
  ): Promise<
    APIResponse<{
      id: string
      nombre: string
      version: string
      activa: boolean
    }>
  > {
    return apiClient.post(`/football/training/models/${modelId}/activate`, {})
  },

  async getDatasetPreview(
    datasetSource: "all" = "all"
  ): Promise<
    APIResponse<{
      samples: Array<{
        id: string
        participant_id: string | null
        level_label: string | null
        split: string | null
        is_synthetic: boolean
        manual_touch_count: number | null
        created_at: string | null
      }>
      total_count: number
      real_count: number
      synthetic_count: number
    }>
  > {
    return apiClient.get(
      `/football/training/dataset-preview?dataset_source=${datasetSource}`
    )
  },
}

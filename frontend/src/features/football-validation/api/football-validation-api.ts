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

  async generateSyntheticDataset(payload: {
    count: number
    train_ratio?: number
    val_ratio?: number
  }): Promise<
    APIResponse<{
      generated_count: number
      splits_summary: Record<string, number>
      levels_summary: Record<string, number>
      samples: Array<{
        id: string
        sample_id: string
        participant_id: string
        level_label: string
        manual_touch_count: number
        split: string
        storage_path: string
        file_size_bytes: number
        duration_s: number
      }>
    }>
  > {
    return apiClient.post("/football/training/generate-synthetic", payload)
  },

  async trainLevelModel(payload: {
    version_tag?: string
    activate?: boolean
    dataset_source?: "all" | "real_only" | "synthetic_only" | "custom_ids"
    sample_ids?: string[]
    skill_id?: string
  }): Promise<
    APIResponse<{
      id: string
      nombre: string
      version: string
      ruta_onnx: string
      activa: boolean
      metricas: {
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
      created_at: string
    }>
  > {
    return apiClient.post("/football/training/train", payload)
  },

  async listModelVersions(): Promise<
    APIResponse<
      Array<{
        id: string
        nombre: string
        version: string
        ruta_onnx: string
        activa: boolean
        metricas: {
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
        created_at: string
      }>
    >
  > {
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
}

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
}

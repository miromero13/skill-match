import { apiClient } from "@/services/api-client"
import type { MetricTypeInfo } from "@/types/catalog"
import type {
  SkillLabConfig,
  SkillLabModel,
  SkillLabSample,
  SkillValidationResult,
  UploadSamplePayload,
} from "../types"

const BASE = "/admin/skill-lab"

/**
 * Cliente del laboratorio de validación por habilidad (solo ADMIN). Los mensajes del
 * sobre APIResponse se muestran textualmente mediante los toasts del `apiClient`.
 */
export const skillLabApi = {
  async getMetricTypes(): Promise<MetricTypeInfo[]> {
    const response = await apiClient.get<MetricTypeInfo[]>(`${BASE}/metric-types`, {
      showToastOnError: false,
    })
    return response.data ?? []
  },

  async getConfig(skillId: string): Promise<SkillLabConfig> {
    const response = await apiClient.get<SkillLabConfig>(`${BASE}/skills/${skillId}`, {
      showToastOnError: true,
    })
    return response.data
  },

  async listSamples(skillId: string): Promise<SkillLabSample[]> {
    const response = await apiClient.get<SkillLabSample[]>(
      `${BASE}/skills/${skillId}/samples`,
      { showToastOnError: true }
    )
    return response.data ?? []
  },

  async uploadSample(skillId: string, payload: UploadSamplePayload): Promise<SkillLabSample> {
    const formData = new FormData()
    formData.append("file", payload.file, payload.file.name)
    formData.append("skill_level_id", payload.skillLevelId)
    formData.append("sample_role", payload.sampleRole)
    if (payload.criterionKey) formData.append("criterion_key", payload.criterionKey)
    if (payload.participantId) formData.append("participant_id", payload.participantId)
    formData.append("signed_consent", String(payload.signedConsent))
    const response = await apiClient.post<SkillLabSample>(
      `${BASE}/skills/${skillId}/samples`,
      formData,
      { showToastOnSuccess: true, showToastOnError: true }
    )
    return response.data
  },

  async deleteSample(sampleId: string): Promise<void> {
    await apiClient.delete<null>(`${BASE}/samples/${sampleId}`, {
      showToastOnSuccess: true,
      showToastOnError: true,
    })
  },

  async train(skillId: string): Promise<SkillLabModel> {
    const response = await apiClient.post<SkillLabModel>(
      `${BASE}/skills/${skillId}/train`,
      undefined,
      { showToastOnSuccess: true, showToastOnError: true }
    )
    return response.data
  },

  async listModels(skillId: string): Promise<SkillLabModel[]> {
    const response = await apiClient.get<SkillLabModel[]>(`${BASE}/skills/${skillId}/models`, {
      showToastOnError: true,
    })
    return response.data ?? []
  },

  /**
   * Valida un video contra toda la configuración de la habilidad. Sin `skillLevelId`
   * el motor detecta el nivel. El análisis puede tardar minutos (fetch no impone timeout).
   * Los fallos de transporte se muestran como aviso en la UI, no como toast.
   */
  async validate(
    skillId: string,
    file: File,
    skillLevelId?: string | null
  ): Promise<SkillValidationResult> {
    const formData = new FormData()
    formData.append("file", file, file.name)
    if (skillLevelId) formData.append("skill_level_id", skillLevelId)
    const response = await apiClient.post<SkillValidationResult>(
      `${BASE}/skills/${skillId}/validate`,
      formData,
      { showToastOnSuccess: true, showToastOnError: false }
    )
    return response.data
  },
}

import { apiClient } from "@/services/api-client"
import type {
  CreateSessionReviewPayload,
  SendSessionTipPayload,
  SessionReview,
  SessionReviewState,
  UserReputation,
} from "@/types/reputation"

export const reputationService = {
  /**
   * Consulta el estado de la reseña para una sesión determinada.
   */
  async getSessionReviewState(sessionId: string): Promise<SessionReviewState> {
    const response = await apiClient.get<SessionReviewState>(`/sessions/${sessionId}/review`)
    return response.data
  },

  /**
   * Emite la calificación pedagógica bilateral (1-5 estrellas en 3 dimensiones).
   */
  async submitSessionReview(
    sessionId: string,
    payload: CreateSessionReviewPayload
  ): Promise<SessionReview> {
    const response = await apiClient.post<SessionReview>(
      `/sessions/${sessionId}/review`,
      payload
    )
    return response.data
  },

  /**
   * Envía una propina voluntaria en SkillPoints al tutor de la sesión.
   */
  async sendSessionTip(
    sessionId: string,
    payload: SendSessionTipPayload
  ): Promise<{ transaction_id: string; amount: number; new_balance: number }> {
    const response = await apiClient.post<{
      transaction_id: string
      amount: number
      new_balance: number
    }>(`/sessions/${sessionId}/tip`, payload)
    return response.data
  },

  /**
   * Obtiene la reputación pública y Puntaje de Confianza de un usuario.
   */
  async getUserReputation(userId: string): Promise<UserReputation> {
    const response = await apiClient.get<UserReputation>(`/users/${userId}/reputation`)
    return response.data
  },
}

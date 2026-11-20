import { apiClient } from "@/services/api-client"
import type { MyPassportSummary, PublicPassport } from "@/types/passport"

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api"

export const passportService = {
  /**
   * Consulta pública de competencias verificadas y dossier técnico (sin autenticación).
   */
  async getPublicPassport(publicUuid: string): Promise<PublicPassport> {
    const response = await apiClient.get<PublicPassport>(`/passports/${publicUuid}`)
    return response.data
  },

  /**
   * Obtiene el resumen y enlaces de pasaporte del miembro autenticado.
   */
  async getMyPassportSummary(): Promise<MyPassportSummary> {
    const response = await apiClient.get<MyPassportSummary>("/passports/me")
    return response.data
  },

  /**
   * Retorna la URL directa del endpoint que genera el código QR en imagen PNG.
   */
  getPassportQrUrl(publicUuid: string): string {
    return `${API_BASE.replace(/\/$/, "")}/passports/${publicUuid}/qr`
  },

  /**
   * Retorna la URL directa del endpoint de descarga del PDF institucional firmado.
   */
  getPassportPdfUrl(publicUuid: string): string {
    return `${API_BASE.replace(/\/$/, "")}/passports/${publicUuid}/pdf`
  },
}

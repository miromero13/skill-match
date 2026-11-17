import { apiClient } from "@/services/api-client"
import type { MatchSuggestion } from "@/types/match"

export function getMatchSuggestions(page: number, signal?: AbortSignal) {
    // apiClient agrega el JWT. signal permite cancelar al salir de la pantalla.
    return apiClient.get<MatchSuggestion[]>("/matches/suggestions", {
        params: { page, page_size: 20 },
        signal,
    })
}

export function getMatchSuggestion(id: string, signal?: AbortSignal) {
    // El detalle usa el ID de la coincidencia, no el ID del otro miembro.
    return apiClient.get<MatchSuggestion>(`/matches/${encodeURIComponent(id)}`, {
        signal,
    })
}
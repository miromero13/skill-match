import { apiClient } from "@/services/api-client"
import type { MatchCompatibility, MatchSuggestion } from "@/types/match"

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

export function getMatchCompatibility(matchId: string, signal?: AbortSignal) {
    return apiClient.get<MatchCompatibility>(`/matches/${encodeURIComponent(matchId)}/compatibility`, {
        signal,
    })
}

export function getUserCompatibility(userId: string, signal?: AbortSignal) {
    return apiClient.get<MatchCompatibility>(`/matches/user/${encodeURIComponent(userId)}/compatibility`, {
        signal,
    })
}

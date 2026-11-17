import { createStore } from "zustand/vanilla"
import { getMatchSuggestion, getMatchSuggestions } from "@/services/match-service"
import type { MatchSuggestion } from "@/types/match"

interface MatchState {
    items: MatchSuggestion[]
    detail: MatchSuggestion | null
    count: number
    page: number
    message: string
    detailMessage: string
    loading: boolean
    loadingDetail: boolean
    failed: boolean
    load: (page: number, signal: AbortSignal) => Promise<void>
    loadDetail: (id: string, signal: AbortSignal) => Promise<void>
}

export function createMatchStore() {
    // Cada pantalla crea su propio store. Al desmontarla se descartan sus datos.
    return createStore<MatchState>()((set) => ({
        items: [],
        detail: null,
        count: 0,
        page: 1,
        message: "",
        detailMessage: "",
        loading: true,
        loadingDetail: false,
        failed: false,

        load: async (page, signal) => {
            // Prepara la pantalla para la página solicitada.
            set({ page, loading: true, failed: false, message: "" })
            try {
                const response = await getMatchSuggestions(page, signal)

                // Ignora la respuesta si la pantalla cambió de página o se cerró.
                if (signal.aborted) return

                set({
                    items: response.data,
                    count: response.count ?? 0,
                    message: response.message,
                    loading: false,
                })
            } catch (error) {
                if (signal.aborted) return

                set({
                    items: [],
                    count: 0,
                    failed: true,
                    loading: false,
                    message: error instanceof Error ? error.message : "No se pudo cargar la lista.",
                })
            }
        },

        loadDetail: async (id, signal) => {
            // Limpia el detalle anterior para que no se muestre en otro cuadro.
            set({ detail: null, detailMessage: "", loadingDetail: true })
            try {
                const response = await getMatchSuggestion(id, signal)
                if (signal.aborted) return

                set({
                    detail: response.data,
                    detailMessage: response.message,
                    loadingDetail: false,
                })
            } catch (error) {
                if (signal.aborted) return

                set({
                    detailMessage:
                        error instanceof Error ? error.message : "No se pudo cargar la coincidencia.",
                    loadingDetail: false,
                })
            }
        },
    }))
}
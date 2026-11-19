import { create } from "zustand"
import { reputationService } from "@/services/reputation-service"
import { useAuthStore } from "@/stores/auth-store"
import type {
  CreateSessionReviewPayload,
  SendSessionTipPayload,
  SessionReview,
  SessionReviewState,
  UserReputation,
} from "@/types/reputation"
import { toast } from "sonner"

interface ReputationStoreState {
  // Estado del modal de reseña
  isReviewModalOpen: boolean
  activeSessionId: string | null
  reviewState: SessionReviewState | null
  isLoadingState: boolean
  isSubmittingReview: boolean
  isSendingTip: boolean

  // Estado del perfil de reputación
  currentReputation: UserReputation | null
  isLoadingReputation: boolean

  // Acciones
  openReviewModal: (sessionId: string) => Promise<void>
  closeReviewModal: () => void
  submitReview: (payload: CreateSessionReviewPayload) => Promise<SessionReview | null>
  sendTip: (payload: SendSessionTipPayload) => Promise<boolean>
  loadUserReputation: (userId: string) => Promise<void>
}

export const useReputationStore = create<ReputationStoreState>((set, get) => ({
  isReviewModalOpen: false,
  activeSessionId: null,
  reviewState: null,
  isLoadingState: false,
  isSubmittingReview: false,
  isSendingTip: false,

  currentReputation: null,
  isLoadingReputation: false,

  openReviewModal: async (sessionId: string) => {
    set({
      isReviewModalOpen: true,
      activeSessionId: sessionId,
      isLoadingState: true,
      reviewState: null,
    })
    try {
      const state = await reputationService.getSessionReviewState(sessionId)
      set({ reviewState: state, isLoadingState: false })
    } catch (error: any) {
      toast.error(error.message || "Error al cargar el estado de la reseña.")
      set({ isLoadingState: false, isReviewModalOpen: false, activeSessionId: null })
    }
  },

  closeReviewModal: () => {
    set({
      isReviewModalOpen: false,
      activeSessionId: null,
      reviewState: null,
    })
  },

  submitReview: async (payload: CreateSessionReviewPayload) => {
    const { activeSessionId } = get()
    if (!activeSessionId) return null

    set({ isSubmittingReview: true })
    try {
      const review = await reputationService.submitSessionReview(activeSessionId, payload)
      toast.success("¡Reseña publicada exitosamente!")
      set({ isSubmittingReview: false })
      return review
    } catch (error: any) {
      toast.error(error.message || "No se pudo publicar la reseña.")
      set({ isSubmittingReview: false })
      return null
    }
  },

  sendTip: async (payload: SendSessionTipPayload) => {
    const { activeSessionId } = get()
    if (!activeSessionId) return false

    set({ isSendingTip: true })
    try {
      await reputationService.sendSessionTip(activeSessionId, payload)
      // Actualizar saldo local en la tienda de autenticación/billetera
      useAuthStore.getState().updateSkillPoints(-payload.amount)
      toast.success(`¡Propina de ${payload.amount} SkillPoints enviada!`)
      set({ isSendingTip: false })
      return true
    } catch (error: any) {
      toast.error(error.message || "Error al transferir la propina.")
      set({ isSendingTip: false })
      return false
    }
  },

  loadUserReputation: async (userId: string) => {
    set({ isLoadingReputation: true })
    try {
      const rep = await reputationService.getUserReputation(userId)
      set({ currentReputation: rep, isLoadingReputation: false })
    } catch (error: any) {
      toast.error(error.message || "Error al consultar la reputación del usuario.")
      set({ isLoadingReputation: false })
    }
  },
}))

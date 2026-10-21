import { create } from "zustand"

export type SwapModality = "virtual" | "in_person"
export type SwapStatus = "pending" | "accepted" | "in_progress" | "completed" | "cancelled" | "disputed"

export interface SwapProposal {
  counterpartId: string
  counterpartName: string
  teachesSkill: string
  learnsSkill: string
  modality: SwapModality
  scheduledDate: string
  scheduledTime: string
  escrowSkillPoints: number
  locationSafePoint?: string
}

interface SwapState {
  currentProposal: SwapProposal | null
  activeSwapsCount: number
  pendingProposalsCount: number

  // Actions
  setProposal: (proposal: SwapProposal) => void
  updateProposal: (updates: Partial<SwapProposal>) => void
  clearProposal: () => void
  setCounts: (active: number, pending: number) => void
}

export const useSwapStore = create<SwapState>((set) => ({
  currentProposal: null,
  activeSwapsCount: 2,
  pendingProposalsCount: 1,

  setProposal: (proposal) => set({ currentProposal: proposal }),

  updateProposal: (updates) =>
    set((state) => ({
      currentProposal: state.currentProposal ? { ...state.currentProposal, ...updates } : null,
    })),

  clearProposal: () => set({ currentProposal: null }),

  setCounts: (active, pending) =>
    set({
      activeSwapsCount: active,
      pendingProposalsCount: pending,
    }),
}))

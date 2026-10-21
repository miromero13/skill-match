import { create } from "zustand"

interface UiState {
  // Mobile drawer states
  isMobileFiltersOpen: boolean
  isMobileMenuOpen: boolean

  // Web sidebar collapse
  isSidebarCollapsed: boolean

  // Modals state
  proposalModal: {
    isOpen: boolean
    counterpartId?: string
    counterpartName?: string
    skillId?: string
  }
  reviewModal: {
    isOpen: boolean
    sessionId?: string
  }
  complaintModal: {
    isOpen: boolean
    sessionId?: string
    defendantId?: string
  }

  // Actions
  toggleMobileFilters: (open?: boolean) => void
  toggleMobileMenu: (open?: boolean) => void
  toggleSidebar: (collapsed?: boolean) => void

  openProposalModal: (counterpartId: string, counterpartName: string, skillId?: string) => void
  closeProposalModal: () => void

  openReviewModal: (sessionId: string) => void
  closeReviewModal: () => void

  openComplaintModal: (sessionId: string, defendantId?: string) => void
  closeComplaintModal: () => void
}

export const useUiStore = create<UiState>((set) => ({
  isMobileFiltersOpen: false,
  isMobileMenuOpen: false,
  isSidebarCollapsed: false,

  proposalModal: {
    isOpen: false,
  },
  reviewModal: {
    isOpen: false,
  },
  complaintModal: {
    isOpen: false,
  },

  toggleMobileFilters: (open) =>
    set((state) => ({
      isMobileFiltersOpen: open !== undefined ? open : !state.isMobileFiltersOpen,
    })),

  toggleMobileMenu: (open) =>
    set((state) => ({
      isMobileMenuOpen: open !== undefined ? open : !state.isMobileMenuOpen,
    })),

  toggleSidebar: (collapsed) =>
    set((state) => ({
      isSidebarCollapsed: collapsed !== undefined ? collapsed : !state.isSidebarCollapsed,
    })),

  openProposalModal: (counterpartId, counterpartName, skillId) =>
    set({
      proposalModal: {
        isOpen: true,
        counterpartId,
        counterpartName,
        skillId,
      },
    }),

  closeProposalModal: () =>
    set({
      proposalModal: {
        isOpen: false,
      },
    }),

  openReviewModal: (sessionId) =>
    set({
      reviewModal: {
        isOpen: true,
        sessionId,
      },
    }),

  closeReviewModal: () =>
    set({
      reviewModal: {
        isOpen: false,
      },
    }),

  openComplaintModal: (sessionId, defendantId) =>
    set({
      complaintModal: {
        isOpen: true,
        sessionId,
        defendantId,
      },
    }),

  closeComplaintModal: () =>
    set({
      complaintModal: {
        isOpen: false,
      },
    }),
}))

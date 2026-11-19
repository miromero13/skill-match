import { create } from 'zustand'
import {
  getWalletBalance,
  getPointPackages,
  topupPoints,
  calculateCashout,
  requestCashout,
  getWalletTransactions,
} from '@/services/wallet-service'
import type {
  PointPackage,
  PointTransaction,
  TransactionFilterType,
  TopupPayload,
  TopupResult,
  CashoutPayload,
  CashoutRequest,
  CashoutCalculation,
} from '@/types/wallet'
import { useAuthStore } from '@/stores/auth-store'
import { useNotificationStore } from '@/stores/notification-store'

interface WalletState {
  balance: number
  escrowBalance: number
  availableBalance: number
  pointsPerUsd: number
  packages: PointPackage[]
  transactions: PointTransaction[]
  filter: TransactionFilterType
  isLoadingBalance: boolean
  isLoadingPackages: boolean
  isLoadingTransactions: boolean
  isTopupModalOpen: boolean
  isCashoutModalOpen: boolean
  isProcessingPayment: boolean
  isProcessingCashout: boolean

  // Actions
  loadBalance: () => Promise<void>
  loadPackages: () => Promise<void>
  loadTransactions: (filter?: TransactionFilterType) => Promise<void>
  setFilter: (filter: TransactionFilterType) => Promise<void>
  processTopup: (payload: TopupPayload) => Promise<TopupResult>
  previewCashout: (points: number) => Promise<CashoutCalculation>
  processCashout: (payload: CashoutPayload) => Promise<CashoutRequest>
  openTopupModal: () => void
  closeTopupModal: () => void
  openCashoutModal: () => void
  closeCashoutModal: () => void
}

function triggerNotificationsAndVibration(title: string, body: string) {
  // 1. Mobile haptic vibration
  if (typeof navigator !== 'undefined' && typeof navigator.vibrate === 'function') {
    try {
      navigator.vibrate([100, 50, 100])
    } catch {
      // Ignore vibration errors
    }
  }

  // 2. Browser Desktop / Chrome Web Notification
  if (typeof window !== 'undefined' && 'Notification' in window) {
    try {
      if (Notification.permission === 'granted') {
        new Notification(title, {
          body,
          icon: '/favicon.ico',
        })
      } else if (Notification.permission !== 'denied') {
        Notification.requestPermission().then((perm) => {
          if (perm === 'granted') {
            new Notification(title, {
              body,
              icon: '/favicon.ico',
            })
          }
        })
      }
    } catch {
      // Ignore notification permissions errors
    }
  }

  // 3. Refresh in-app unread notifications
  try {
    useNotificationStore.getState().loadUnread?.()
    useNotificationStore.getState().loadList?.()
  } catch {
    // Ignore in-app notification refresh errors
  }
}

export const useWalletStore = create<WalletState>((set, get) => ({
  balance: 0,
  escrowBalance: 0,
  availableBalance: 0,
  pointsPerUsd: 10,
  packages: [],
  transactions: [],
  filter: 'ALL',
  isLoadingBalance: false,
  isLoadingPackages: false,
  isLoadingTransactions: false,
  isTopupModalOpen: false,
  isCashoutModalOpen: false,
  isProcessingPayment: false,
  isProcessingCashout: false,

  loadBalance: async () => {
    set({ isLoadingBalance: true })
    try {
      const data = await getWalletBalance()
      set({
        balance: data.balance,
        escrowBalance: data.escrow_balance,
        availableBalance: data.available_balance,
        pointsPerUsd: data.points_per_usd || 10,
      })
      // Sync with global auth store balance
      useAuthStore.getState().updateProfile({
        skillPointsBalance: data.balance,
      })
    } catch {
      // Error handled by apiClient toast
    } finally {
      set({ isLoadingBalance: false })
    }
  },

  loadPackages: async () => {
    set({ isLoadingPackages: true })
    try {
      const packages = await getPointPackages()
      set({ packages })
    } catch {
      // Error handled by apiClient toast
    } finally {
      set({ isLoadingPackages: false })
    }
  },

  loadTransactions: async (newFilter) => {
    const activeFilter = newFilter || get().filter
    set({ isLoadingTransactions: true })
    try {
      const transactions = await getWalletTransactions(activeFilter)
      set({ transactions, filter: activeFilter })
    } catch {
      // Error handled by apiClient toast
    } finally {
      set({ isLoadingTransactions: false })
    }
  },

  setFilter: async (filter) => {
    set({ filter })
    await get().loadTransactions(filter)
  },

  processTopup: async (payload) => {
    set({ isProcessingPayment: true })
    try {
      const result = await topupPoints(payload)
      // Refresh local balance and transaction list
      await Promise.all([get().loadBalance(), get().loadTransactions()])

      // Trigger multi-platform notifications
      triggerNotificationsAndVibration(
        '¡Recarga de SkillPoints Exitosa!',
        `Se han acreditado +${result.points_added} SP a tu billetera. Saldo actual: ${result.new_balance} SP.`
      )

      return result
    } finally {
      set({ isProcessingPayment: false })
    }
  },

  previewCashout: async (points: number) => {
    return await calculateCashout(points)
  },

  processCashout: async (payload) => {
    set({ isProcessingCashout: true })
    try {
      const request = await requestCashout(payload)
      // Refresh balance and transactions
      await Promise.all([get().loadBalance(), get().loadTransactions()])

      triggerNotificationsAndVibration(
        'Solicitud de Retiro Registrada',
        `Has solicitado retirar ${request.points} SP ($${request.net_usd.toFixed(2)} USD netos). Procesamiento en 24-48h hábiles.`
      )

      return request
    } finally {
      set({ isProcessingCashout: false })
    }
  },

  openTopupModal: () => set({ isTopupModalOpen: true }),
  closeTopupModal: () => set({ isTopupModalOpen: false }),
  openCashoutModal: () => set({ isCashoutModalOpen: true }),
  closeCashoutModal: () => set({ isCashoutModalOpen: false }),
}))

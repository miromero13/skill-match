/**
 * Tienda Zustand para la gestión de quejas ciudadanas y resolución de disputas
 * (HU-43 / RF-GOV-01, RF-GOV-02, RF-GOV-03).
 */
import { create } from 'zustand'
import type {
  Complaint,
  ComplaintCreatePayload,
  ComplaintResolvePayload,
} from '@/types/complaint'
import {
  getMyComplaints,
  submitComplaint,
  getAdminComplaints,
  getAdminComplaintDetail,
  resolveComplaint,
} from '@/services/complaint-service'

interface ComplaintState {
  // Estado para Miembros (HU-43 / Vistas 24A, 26A)
  memberComplaints: Complaint[]
  memberTotal: number
  isLoadingMember: boolean
  isSubmitting: boolean

  // Estado para Administrador / Arbitraje (HU-43 / Vistas 18, 20)
  adminComplaints: Complaint[]
  adminTotal: number
  selectedComplaint: Complaint | null
  isLoadingAdmin: boolean
  isResolving: boolean
  statusFilter: string

  // Acciones de Miembros
  loadMyComplaints: () => Promise<void>
  createComplaint: (payload: ComplaintCreatePayload) => Promise<boolean>

  // Acciones de Administrador
  setStatusFilter: (filter: string) => void
  loadAdminComplaints: (filterOverride?: string) => Promise<void>
  selectComplaint: (complaint: Complaint | null) => void
  loadComplaintDetail: (id: string) => Promise<void>
  resolveComplaintAction: (
    id: string,
    payload: ComplaintResolvePayload
  ) => Promise<boolean>
}

export const useComplaintStore = create<ComplaintState>((set, get) => ({
  memberComplaints: [],
  memberTotal: 0,
  isLoadingMember: false,
  isSubmitting: false,

  adminComplaints: [],
  adminTotal: 0,
  selectedComplaint: null,
  isLoadingAdmin: false,
  isResolving: false,
  statusFilter: 'ALL',

  loadMyComplaints: async () => {
    set({ isLoadingMember: true })
    try {
      const { items, total } = await getMyComplaints(1, 50)
      set({ memberComplaints: items, memberTotal: total })
    } catch {
      // Error manejado en apiClient
    } finally {
      set({ isLoadingMember: false })
    }
  },

  createComplaint: async (payload: ComplaintCreatePayload) => {
    set({ isSubmitting: true })
    try {
      const newComplaint = await submitComplaint(payload)
      set((state) => ({
        memberComplaints: [newComplaint, ...state.memberComplaints],
        memberTotal: state.memberTotal + 1,
      }))
      return true
    } catch {
      return false
    } finally {
      set({ isSubmitting: false })
    }
  },

  setStatusFilter: (filter: string) => {
    set({ statusFilter: filter })
    get().loadAdminComplaints(filter)
  },

  loadAdminComplaints: async (filterOverride?: string) => {
    set({ isLoadingAdmin: true })
    try {
      const filter = filterOverride ?? get().statusFilter
      const { items, total } = await getAdminComplaints(filter, 1, 50)
      set({
        adminComplaints: items,
        adminTotal: total,
        // Si hay una queja seleccionada, actualizar sus datos si está en la lista
        selectedComplaint:
          items.find((c) => c.id === get().selectedComplaint?.id) ??
          (items.length > 0 ? items[0] : null),
      })
    } catch {
      // Error manejado en apiClient
    } finally {
      set({ isLoadingAdmin: false })
    }
  },

  selectComplaint: (complaint: Complaint | null) => {
    set({ selectedComplaint: complaint })
  },

  loadComplaintDetail: async (id: string) => {
    try {
      const detail = await getAdminComplaintDetail(id)
      set({ selectedComplaint: detail })
    } catch {
      // Error manejado en apiClient
    }
  },

  resolveComplaintAction: async (id: string, payload: ComplaintResolvePayload) => {
    set({ isResolving: true })
    try {
      const updated = await resolveComplaint(id, payload)
      set((state) => ({
        selectedComplaint: updated,
        adminComplaints: state.adminComplaints.map((c) =>
          c.id === updated.id ? updated : c
        ),
      }))
      return true
    } catch {
      return false
    } finally {
      set({ isResolving: false })
    }
  },
}))

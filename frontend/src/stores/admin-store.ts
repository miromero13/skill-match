import { create } from "zustand"
import {
  type AdminUser,
  type CreateAdminPayload,
  getAdministrators,
  createAdministrator,
  updateAdministratorStatus,
} from "@/services/admin-service"

interface AdminStoreState {
  administrators: AdminUser[]
  totalCount: number
  isLoading: boolean
  isSubmitting: boolean
  error: string | null
  searchTerm: string
  isCreateModalOpen: boolean

  // Actions
  setSearchTerm: (term: string) => void
  setIsCreateModalOpen: (open: boolean) => void
  clearError: () => void
  fetchAdministrators: () => Promise<void>
  createAdmin: (payload: CreateAdminPayload) => Promise<boolean>
  toggleStatus: (adminId: string, is_active: boolean, reason?: string) => Promise<boolean>
}

export const useAdminStore = create<AdminStoreState>((set, get) => ({
  administrators: [],
  totalCount: 0,
  isLoading: false,
  isSubmitting: false,
  error: null,
  searchTerm: "",
  isCreateModalOpen: false,

  setSearchTerm: (term: string) => set({ searchTerm: term }),

  setIsCreateModalOpen: (open: boolean) => set({ isCreateModalOpen: open, error: null }),

  clearError: () => set({ error: null }),

  fetchAdministrators: async () => {
    set({ isLoading: true, error: null })
    try {
      const { items, count } = await getAdministrators()
      set({ administrators: items, totalCount: count, isLoading: false })
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error al obtener administradores"
      set({ error: message, isLoading: false })
    }
  },

  createAdmin: async (payload: CreateAdminPayload) => {
    // Validación de unicidad de correo gestionada en Zustand (HU-10)
    const { administrators } = get()
    const isDuplicate = administrators.some(
      (a) => a.email.toLowerCase() === payload.email.trim().toLowerCase()
    )
    if (isDuplicate) {
      const errorMsg = "El correo electrónico ya se encuentra registrado en el directorio administrativo."
      set({ error: errorMsg, isSubmitting: false })
      return false
    }

    set({ isSubmitting: true, error: null })
    try {
      const newAdmin = await createAdministrator(payload)
      // Actualizar estado local inmediatamente
      set((state) => ({
        administrators: [newAdmin, ...state.administrators],
        totalCount: state.totalCount + 1,
        isSubmitting: false,
        isCreateModalOpen: false,
        error: null,
      }))
      return true
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error al crear administrador"
      set({ error: message, isSubmitting: false })
      return false
    }
  },

  toggleStatus: async (adminId: string, is_active: boolean, reason?: string) => {
    try {
      const updatedAdmin = await updateAdministratorStatus(adminId, { is_active, reason })
      // Actualizar estado reactivamente en la lista
      set((state) => ({
        administrators: state.administrators.map((admin) =>
          admin.id === adminId ? { ...admin, is_active: updatedAdmin.is_active } : admin
        ),
      }))
      return true
    } catch {
      return false
    }
  },
}))

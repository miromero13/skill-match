import { create } from "zustand"
import {
  type AdminUser,
  type CreateAdminPayload,
  getAdministrators,
  createAdministrator,
  updateAdministratorStatus,
} from "@/services/admin-service"

export interface DirectorySkill {
  name: string
  level?: string // e.g. "L5", "L4", "L3"
  isVerified?: boolean
}

export interface DirectoryUser {
  id: string
  full_name: string
  email: string
  role: "ADMIN" | "MEMBER"
  is_active: boolean
  status_label?: string
  skills?: DirectorySkill[]
  is_locked?: boolean
}

// Datos canónicos del Directorio fieles a Vista 15A & 17A
const SEED_DIRECTORY_USERS: DirectoryUser[] = [
  {
    id: "seed-martin-silva",
    full_name: "Martín Silva",
    email: "martin@dev.io",
    role: "MEMBER",
    is_active: true,
    status_label: "Activo",
    skills: [
      { name: "Python", level: "L5", isVerified: true },
      { name: "Docker", level: "L4", isVerified: true },
      { name: "Rust", isVerified: false },
    ],
  },
  {
    id: "seed-sofia-rodriguez",
    full_name: "Sofía Rodríguez",
    email: "sofia@guitar.com",
    role: "MEMBER",
    is_active: true,
    status_label: "Activo",
    skills: [
      { name: "Guitarra Flamenca", level: "L3", isVerified: true },
    ],
  },
  {
    id: "seed-lucas-vega",
    full_name: "Lucas Vega",
    email: "lucas@tokio.rs",
    role: "MEMBER",
    is_active: true,
    status_label: "En Disputa",
    skills: [
      { name: "Rust Concurrente", isVerified: false },
    ],
  },
  {
    id: "seed-carla-dominguez",
    full_name: "Carla Domínguez",
    email: "carla@design.org",
    role: "MEMBER",
    is_active: true,
    status_label: "Activo (0 Habilidades)",
    skills: [],
  },
  {
    id: "seed-laura-benitez",
    full_name: "Laura Benítez",
    email: "laura@admin.sm",
    role: "ADMIN",
    is_active: true,
    status_label: "SuperAdmin Activo",
    skills: [],
  },
  {
    id: "seed-esteban-rios",
    full_name: "Esteban Ríos",
    email: "esteban@cheat.net",
    role: "MEMBER",
    is_active: false,
    status_label: "Suspendido (7d)",
    skills: [
      { name: "Python", isVerified: false },
    ],
  },
]

interface AdminStoreState {
  users: DirectoryUser[]
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
  toggleStatus: (userId: string, is_active: boolean, reason?: string) => Promise<boolean>
}

export const useAdminStore = create<AdminStoreState>((set, get) => ({
  users: SEED_DIRECTORY_USERS,
  totalCount: SEED_DIRECTORY_USERS.length,
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
      const { items } = await getAdministrators()

      // Sincronizar administradores reales del backend con el directorio de 15A
      const emailMap = new Map<string, DirectoryUser>()

      // 1. Cargar usuarios base de la maqueta
      SEED_DIRECTORY_USERS.forEach((user) => {
        emailMap.set(user.email.toLowerCase(), { ...user })
      })

      // 2. Incorporar administradores devueltos por el backend
      items.forEach((admin: AdminUser) => {
        const cleanEmail = admin.email.toLowerCase()
        const existing = emailMap.get(cleanEmail)
        if (existing) {
          emailMap.set(cleanEmail, {
            ...existing,
            id: admin.id,
            full_name: admin.full_name,
            role: "ADMIN",
            is_active: admin.is_active,
            status_label: admin.is_active
              ? existing.status_label || "Activo"
              : "Suspendido",
          })
        } else {
          // Administrador nuevo creado en backend
          emailMap.set(cleanEmail, {
            id: admin.id,
            full_name: admin.full_name,
            email: admin.email,
            role: "ADMIN",
            is_active: admin.is_active,
            status_label: admin.is_active ? "Activo" : "Suspendido",
            skills: [],
          })
        }
      })

      const combinedUsers = Array.from(emailMap.values())
      set({
        users: combinedUsers,
        totalCount: combinedUsers.length,
        isLoading: false,
      })
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error al sincronizar directorio"
      set({ error: message, isLoading: false })
    }
  },

  createAdmin: async (payload: CreateAdminPayload) => {
    // Validación de unicidad de correo en la tienda Zustand (HU-10)
    const { users } = get()
    const cleanEmail = payload.email.trim().toLowerCase()
    const isDuplicate = users.some((u) => u.email.toLowerCase() === cleanEmail)
    if (isDuplicate) {
      const errorMsg = "El correo electrónico ya se encuentra registrado en el directorio administrativo."
      set({ error: errorMsg, isSubmitting: false })
      return false
    }

    set({ isSubmitting: true, error: null })
    try {
      const newAdmin = await createAdministrator(payload)
      const newEntry: DirectoryUser = {
        id: newAdmin.id,
        full_name: newAdmin.full_name,
        email: newAdmin.email,
        role: "ADMIN",
        is_active: true,
        status_label: "Activo",
        skills: [],
      }

      set((state) => ({
        users: [newEntry, ...state.users],
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

  toggleStatus: async (userId: string, is_active: boolean, reason?: string) => {
    try {
      const targetUser = get().users.find((u) => u.id === userId)
      if (targetUser && !userId.startsWith("seed-")) {
        await updateAdministratorStatus(userId, { is_active, reason })
      }

      // Actualizar estado reactivo en memoria
      set((state) => ({
        users: state.users.map((user) => {
          if (user.id !== userId) return user
          return {
            ...user,
            is_active,
            status_label: is_active ? "Activo" : "Suspendido",
          }
        }),
      }))
      return true
    } catch {
      return false
    }
  },
}))

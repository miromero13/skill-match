import { create } from "zustand"
import { persist, createJSONStorage } from "zustand/middleware"

export type UserRole = "MEMBER" | "ADMIN"

export interface UserProfile {
  id: string
  email: string
  fullName: string
  avatarUrl?: string
  role: UserRole
  skillPointsBalance: number
  reputationScore: number // e.g. 4.9
  trustLevel: number // 1 to 5
  isVerified: boolean
}

interface AuthState {
  user: UserProfile | null
  token: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  isLoading: boolean

  // Actions
  login: (user: UserProfile, token: string, refreshToken?: string) => void
  logout: () => void
  updateProfile: (updates: Partial<UserProfile>) => void
  updateSkillPoints: (delta: number) => void
  setLoading: (loading: boolean) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: false,

      login: (user, token, refreshToken) =>
        set({
          user,
          token,
          refreshToken: refreshToken || null,
          isAuthenticated: true,
          isLoading: false,
        }),

      logout: () =>
        set({
          user: null,
          token: null,
          refreshToken: null,
          isAuthenticated: false,
          isLoading: false,
        }),

      updateProfile: (updates) =>
        set((state) => ({
          user: state.user ? { ...state.user, ...updates } : null,
        })),

      updateSkillPoints: (delta) =>
        set((state) => ({
          user: state.user
            ? {
                ...state.user,
                skillPointsBalance: Math.max(0, state.user.skillPointsBalance + delta),
              }
            : null,
        })),

      setLoading: (loading) => set({ isLoading: loading }),
    }),
    {
      name: "skillmatch-auth-storage",
      storage: createJSONStorage(() => localStorage),
    }
  )
)

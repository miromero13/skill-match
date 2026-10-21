import { create } from "zustand"
import { persist, createJSONStorage } from "zustand/middleware"

export type UserRole = "member" | "admin" | "superadmin"

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
  isAuthenticated: boolean
  isLoading: boolean

  // Actions
  login: (user: UserProfile, token: string) => void
  logout: () => void
  updateProfile: (updates: Partial<UserProfile>) => void
  updateSkillPoints: (delta: number) => void
  setLoading: (loading: boolean) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: {
        id: "usr_mock_1",
        email: "ilseromero35@gmail.com",
        fullName: "Ilse Romero",
        avatarUrl: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&h=100&fit=crop",
        role: "member",
        skillPointsBalance: 120,
        reputationScore: 4.9,
        trustLevel: 4,
        isVerified: true,
      },
      token: "mock_jwt_token_skillmatch",
      isAuthenticated: true,
      isLoading: false,

      login: (user, token) =>
        set({
          user,
          token,
          isAuthenticated: true,
          isLoading: false,
        }),

      logout: () =>
        set({
          user: null,
          token: null,
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

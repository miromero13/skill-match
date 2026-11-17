import { create } from "zustand"
import { userModerationService } from "@/services/user-moderation-service"
import type {
    BlockedUser,
    ReportUserPayload,
    ReportUserResult,
    UserSafetyStatus,
} from "@/types/user-moderation"

interface UserModerationState {
    blockedUsers: BlockedUser[]
    count: number
    loading: boolean
    error: string | null
    safetyCache: Record<string, UserSafetyStatus>

    fetchBlockedUsers: () => Promise<void>
    blockUser: (userId: string, reason?: string, notes?: string) => Promise<boolean>
    unblockUser: (userId: string) => Promise<boolean>
    reportUser: (userId: string, payload: ReportUserPayload) => Promise<ReportUserResult | null>
    fetchSafetyStatus: (userId: string) => Promise<UserSafetyStatus | null>
}

export const useUserModerationStore = create<UserModerationState>((set, get) => ({
    blockedUsers: [],
    count: 0,
    loading: false,
    error: null,
    safetyCache: {},

    fetchBlockedUsers: async () => {
        set({ loading: true, error: null })
        try {
            const res = await userModerationService.getBlockedUsers()
            set({
                blockedUsers: res.data,
                count: res.count ?? res.data.length,
                loading: false,
            })
        } catch (err) {
            set({
                loading: false,
                error: err instanceof Error ? err.message : "Error al cargar usuarios bloqueados",
            })
        }
    },

    blockUser: async (userId: string, reason?: string, notes?: string) => {
        try {
            const res = await userModerationService.blockUser(userId, reason, notes)
            const newBlock = res.data
            set((state) => ({
                blockedUsers: [
                    newBlock,
                    ...state.blockedUsers.filter((u) => u.user_id !== userId),
                ],
                count: state.count + 1,
                safetyCache: {
                    ...state.safetyCache,
                    [userId]: {
                        target_user_id: userId,
                        is_blocked_by_me: true,
                        is_blocking_me: state.safetyCache[userId]?.is_blocking_me ?? false,
                        can_interact: false,
                        blocked_at: newBlock.blocked_at,
                    },
                },
            }))
            return true
        } catch {
            return false
        }
    },

    unblockUser: async (userId: string) => {
        try {
            await userModerationService.unblockUser(userId)
            set((state) => ({
                blockedUsers: state.blockedUsers.filter((u) => u.user_id !== userId),
                count: Math.max(0, state.count - 1),
                safetyCache: {
                    ...state.safetyCache,
                    [userId]: {
                        target_user_id: userId,
                        is_blocked_by_me: false,
                        is_blocking_me: state.safetyCache[userId]?.is_blocking_me ?? false,
                        can_interact: !(state.safetyCache[userId]?.is_blocking_me ?? false),
                        blocked_at: null,
                    },
                },
            }))
            return true
        } catch {
            return false
        }
    },

    reportUser: async (userId: string, payload: ReportUserPayload) => {
        try {
            const res = await userModerationService.reportUser(userId, payload)
            if (payload.block_user) {
                await get().fetchBlockedUsers()
            }
            return res.data
        } catch {
            return null
        }
    },

    fetchSafetyStatus: async (userId: string) => {
        const cached = get().safetyCache[userId]
        if (cached) return cached

        try {
            const res = await userModerationService.getSafetyStatus(userId)
            set((state) => ({
                safetyCache: { ...state.safetyCache, [userId]: res.data },
            }))
            return res.data
        } catch {
            return null
        }
    },
}))

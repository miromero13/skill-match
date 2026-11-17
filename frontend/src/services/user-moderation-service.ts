import { apiClient } from "@/services/api-client"
import type { APIResponse } from "@/types/api"
import type {
    BlockedUser,
    ReportUserPayload,
    ReportUserResult,
    UserSafetyStatus,
} from "@/types/user-moderation"

export const userModerationService = {
    async getBlockedUsers(signal?: AbortSignal): Promise<APIResponse<BlockedUser[]>> {
        return apiClient.get<BlockedUser[]>("/users/blocked", { signal })
    },

    async blockUser(
        userId: string,
        reason?: string,
        notes?: string
    ): Promise<APIResponse<BlockedUser>> {
        return apiClient.post<BlockedUser>(`/users/${encodeURIComponent(userId)}/block`, {
            reason,
            notes,
        })
    },

    async unblockUser(userId: string): Promise<APIResponse<null>> {
        return apiClient.delete<null>(`/users/${encodeURIComponent(userId)}/unblock`)
    },

    async reportUser(
        userId: string,
        payload: ReportUserPayload
    ): Promise<APIResponse<ReportUserResult>> {
        return apiClient.post<ReportUserResult>(
            `/users/${encodeURIComponent(userId)}/report`,
            payload
        )
    },

    async getSafetyStatus(
        userId: string,
        signal?: AbortSignal
    ): Promise<APIResponse<UserSafetyStatus>> {
        return apiClient.get<UserSafetyStatus>(
            `/users/${encodeURIComponent(userId)}/safety-status`,
            { signal }
        )
    },
}

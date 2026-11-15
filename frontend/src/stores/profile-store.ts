import { create } from "zustand"
import { getAuthSessionVersion, useAuthStore } from "@/stores/auth-store"
import {
  deleteMyAvailabilitySlot,
  enrollMyBiometrics,
  getMyAvailability,
  getMyProfile,
  patchMyProfile,
  replaceMyAvailability,
  updateMyProfile,
} from "@/services/profile-service"
import type {
  AvailabilityMatrixPayload,
  AvailabilitySlot,
  BiometricEnrollPayload,
  UserProfileData,
  UserProfilePatchPayload,
  UserProfileUpdatePayload,
} from "@/types/profile"

interface ProfileState {
  profile: UserProfileData | null
  availabilitySlots: AvailabilitySlot[]
  availabilityCount: number
  isLoadingProfile: boolean
  isSavingProfile: boolean
  isEnrollingBiometrics: boolean
  isLoadingAvailability: boolean
  isSavingAvailability: boolean
  loadProfile: () => Promise<void>
  saveProfile: (payload: UserProfileUpdatePayload) => Promise<boolean>
  patchProfile: (payload: UserProfilePatchPayload) => Promise<boolean>
  enrollBiometrics: (payload: BiometricEnrollPayload) => Promise<boolean>
  loadAvailability: () => Promise<void>
  saveAvailability: (payload: AvailabilityMatrixPayload) => Promise<boolean>
  removeAvailabilitySlot: (slotId: string) => Promise<boolean>
}

let sessionEpoch = 0

export const useProfileStore = create<ProfileState>((set, get) => ({
  profile: null,
  availabilitySlots: [],
  availabilityCount: 0,
  isLoadingProfile: false,
  isSavingProfile: false,
  isEnrollingBiometrics: false,
  isLoadingAvailability: false,
  isSavingAvailability: false,

  loadProfile: async () => {
    if (get().isLoadingProfile) return
    const epoch = sessionEpoch
    set({ isLoadingProfile: true })
    try {
      const data = await getMyProfile()
      if (epoch !== sessionEpoch) return
      set({ profile: data })
    } catch {
      // El toast de error lo gestiona apiClient
    } finally {
      if (epoch === sessionEpoch) set({ isLoadingProfile: false })
    }
  },

  saveProfile: async (payload) => {
    if (get().isSavingProfile) return false
    const epoch = sessionEpoch
    set({ isSavingProfile: true })
    try {
      const updated = await updateMyProfile(payload)
      if (epoch !== sessionEpoch) return false
      set({ profile: updated })
      const currentAuthUser = useAuthStore.getState().user
      if (currentAuthUser) {
        useAuthStore.getState().updateProfile({
          fullName: updated.full_name,
          avatarUrl: updated.avatar_url ?? undefined,
        })
      }
      return true
    } catch {
      return false
    } finally {
      if (epoch === sessionEpoch) set({ isSavingProfile: false })
    }
  },

  patchProfile: async (payload) => {
    if (get().isSavingProfile) return false
    const epoch = sessionEpoch
    set({ isSavingProfile: true })
    try {
      const updated = await patchMyProfile(payload)
      if (epoch !== sessionEpoch) return false
      set({ profile: updated })
      const currentAuthUser = useAuthStore.getState().user
      if (currentAuthUser) {
        useAuthStore.getState().updateProfile({
          fullName: updated.full_name,
          avatarUrl: updated.avatar_url ?? undefined,
        })
      }
      return true
    } catch {
      return false
    } finally {
      if (epoch === sessionEpoch) set({ isSavingProfile: false })
    }
  },

  enrollBiometrics: async (payload) => {
    if (get().isEnrollingBiometrics) return false
    const epoch = sessionEpoch
    set({ isEnrollingBiometrics: true })
    try {
      const updated = await enrollMyBiometrics(payload)
      if (epoch !== sessionEpoch) return false
      set({ profile: updated })
      return true
    } catch {
      return false
    } finally {
      if (epoch === sessionEpoch) set({ isEnrollingBiometrics: false })
    }
  },

  loadAvailability: async () => {
    if (get().isLoadingAvailability) return
    const epoch = sessionEpoch
    set({ isLoadingAvailability: true })
    try {
      const { slots, count } = await getMyAvailability()
      if (epoch !== sessionEpoch) return
      set({ availabilitySlots: slots, availabilityCount: count })
    } catch {
      // Manejado por apiClient
    } finally {
      if (epoch === sessionEpoch) set({ isLoadingAvailability: false })
    }
  },

  saveAvailability: async (payload) => {
    if (get().isSavingAvailability) return false
    const epoch = sessionEpoch
    set({ isSavingAvailability: true })
    try {
      const { slots, count } = await replaceMyAvailability(payload)
      if (epoch !== sessionEpoch) return false
      set({ availabilitySlots: slots, availabilityCount: count })
      if (payload.timezone || payload.buffer_minutes !== undefined) {
        await get().loadProfile()
      }
      return true
    } catch {
      return false
    } finally {
      if (epoch === sessionEpoch) set({ isSavingAvailability: false })
    }
  },

  removeAvailabilitySlot: async (slotId) => {
    if (get().isSavingAvailability) return false
    const epoch = sessionEpoch
    set({ isSavingAvailability: true })
    try {
      await deleteMyAvailabilitySlot(slotId)
      if (epoch !== sessionEpoch) return false
      const remaining = get().availabilitySlots.filter((s) => s.id !== slotId)
      set({
        availabilitySlots: remaining,
        availabilityCount: remaining.length,
      })
      return true
    } catch {
      return false
    } finally {
      if (epoch === sessionEpoch) set({ isSavingAvailability: false })
    }
  },
}))

let authVersion = getAuthSessionVersion()
useAuthStore.subscribe((state, previous) => {
  if (
    authVersion !== getAuthSessionVersion() ||
    state.user?.id !== previous.user?.id ||
    state.user?.role !== previous.user?.role ||
    state.isAuthenticated !== previous.isAuthenticated
  ) {
    authVersion = getAuthSessionVersion()
    sessionEpoch++
    useProfileStore.setState({
      profile: null,
      availabilitySlots: [],
      availabilityCount: 0,
      isLoadingProfile: false,
      isSavingProfile: false,
      isEnrollingBiometrics: false,
      isLoadingAvailability: false,
      isSavingAvailability: false,
    })
  }
})

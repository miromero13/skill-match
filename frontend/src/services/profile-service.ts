import { apiClient } from "@/services/api-client"
import type {
  AvailabilityMatrixPayload,
  AvailabilitySlot,
  BiometricEnrollPayload,
  IdentityVerifyPayload,
  UserProfileData,
  UserProfilePatchPayload,
  UserProfileUpdatePayload,
} from "@/types/profile"

const profileEndpoint = "/users/me/profile"
const biometricsEndpoint = "/users/me/biometrics/enroll"
const identityVerifyEndpoint = "/users/me/identity/verify"
const availabilityEndpoint = "/users/me/availability"

const mutationOptions = {
  showToastOnError: true,
  showToastOnSuccess: true,
}

export async function getMyProfile(): Promise<UserProfileData> {
  const response = await apiClient.get<UserProfileData>(profileEndpoint, {
    showToastOnError: true,
  })
  return response.data
}

export async function updateMyProfile(
  payload: UserProfileUpdatePayload
): Promise<UserProfileData> {
  const response = await apiClient.put<UserProfileData>(
    profileEndpoint,
    payload,
    mutationOptions
  )
  return response.data
}

export async function patchMyProfile(
  payload: UserProfilePatchPayload
): Promise<UserProfileData> {
  const response = await apiClient.patch<UserProfileData>(
    profileEndpoint,
    payload,
    mutationOptions
  )
  return response.data
}

export async function enrollMyBiometrics(
  payload: BiometricEnrollPayload
): Promise<UserProfileData> {
  const response = await apiClient.post<UserProfileData>(
    biometricsEndpoint,
    payload,
    mutationOptions
  )
  return response.data
}

export async function verifyMyIdentity(
  payload: IdentityVerifyPayload
): Promise<UserProfileData> {
  const response = await apiClient.post<UserProfileData>(
    identityVerifyEndpoint,
    payload,
    mutationOptions
  )
  return response.data
}

export async function getMyAvailability(): Promise<{
  slots: AvailabilitySlot[]
  count: number
}> {
  const response = await apiClient.get<AvailabilitySlot[]>(
    availabilityEndpoint,
    { showToastOnError: true }
  )
  return {
    slots: response.data ?? [],
    count: response.count ?? (response.data ? response.data.length : 0),
  }
}

export async function replaceMyAvailability(
  payload: AvailabilityMatrixPayload
): Promise<{
  slots: AvailabilitySlot[]
  count: number
}> {
  const response = await apiClient.put<AvailabilitySlot[]>(
    availabilityEndpoint,
    payload,
    mutationOptions
  )
  return {
    slots: response.data ?? [],
    count: response.count ?? (response.data ? response.data.length : 0),
  }
}

export async function deleteMyAvailabilitySlot(slotId: string): Promise<void> {
  await apiClient.delete<null>(
    `${availabilityEndpoint}/${slotId}`,
    mutationOptions
  )
}

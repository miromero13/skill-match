import { apiClient } from "@/services/api-client"
import { useAuthStore } from "@/stores/auth-store"

export interface AdminLoginCredentials {
  email: string
  password: string
  remember_me?: boolean
}

export interface AdminUserDto {
  id: string
  email: string
  full_name: string
  role: "ADMIN"
  is_active: boolean
  avatar_url?: string | null
}

export interface AdminTokenDataDto {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: AdminUserDto
}

export async function loginAdmin(credentials: AdminLoginCredentials): Promise<AdminTokenDataDto> {
  const response = await apiClient.post<AdminTokenDataDto>("/admin/auth/login", {
    body: credentials,
    showToastOnError: false, // Manejado de forma contextual en el formulario
    showToastOnSuccess: false,
  })

  const tokenData = response.data

  // Guardar en Zustand con rol canónico ADMIN
  useAuthStore.getState().login(
    {
      id: tokenData.user.id,
      email: tokenData.user.email,
      fullName: tokenData.user.full_name,
      avatarUrl: tokenData.user.avatar_url || undefined,
      role: "ADMIN",
      skillPointsBalance: 0,
      reputationScore: 5.0,
      trustLevel: 5,
      isVerified: true,
    },
    tokenData.access_token,
    tokenData.refresh_token
  )

  return tokenData
}

import { apiClient } from "@/services/api-client"
import { useAuthStore, type UserRole } from "@/stores/auth-store"
import { toast } from "sonner"

export interface UserMeDto {
  id: string
  email: string
  full_name: string
  role: UserRole
  is_active: boolean
  avatar_url?: string | null
  phone_number?: string | null
  provider?: string | null
}

export interface TokenRefreshResponseDto {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface GoogleAuthResponseDto {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: UserMeDto
}

/**
 * Autentica o registra a un miembro de la comunidad mediante Google OAuth (POST /api/auth/oauth/google).
 */
export async function loginWithGoogle(idToken: string): Promise<GoogleAuthResponseDto> {
  const response = await apiClient.post<GoogleAuthResponseDto>(
    "/auth/oauth/google",
    { id_token: idToken },
    {
      showToastOnError: true,
      showToastOnSuccess: true,
      successMessage: "¡Bienvenido a SkillMatch!",
    }
  )

  const authData = response.data

  useAuthStore.getState().login(
    {
      id: authData.user.id,
      email: authData.user.email,
      fullName: authData.user.full_name,
      role: authData.user.role,
      avatarUrl: authData.user.avatar_url || undefined,
      skillPointsBalance: 150, // Bono de bienvenida inicial (3 validaciones gratis)
      reputationScore: 5.0,
      trustLevel: 1,
      isVerified: true,
    },
    authData.access_token,
    authData.refresh_token
  )

  return authData
}


/**
 * Consulta la identidad y perfil del usuario autenticado actual (GET /api/auth/me).
 * Sincroniza la información devuelta con useAuthStore.
 */
export async function getMe(): Promise<UserMeDto> {
  const response = await apiClient.get<UserMeDto>("/auth/me", {
    showToastOnError: false,
    showToastOnSuccess: false,
  })

  const me = response.data

  // Sincronizar perfil con Zustand
  useAuthStore.getState().updateProfile({
    id: me.id,
    email: me.email,
    fullName: me.full_name,
    role: me.role,
    avatarUrl: me.avatar_url || undefined,
    isVerified: true,
  })

  return me
}

/**
 * Cierra la sesión activa en el servidor y limpia el estado local de Zustand (POST /api/auth/logout).
 * Garantiza la limpieza local incluso ante caídas de conexión.
 */
export async function logoutSession(): Promise<void> {
  const refreshToken = useAuthStore.getState().refreshToken

  try {
    await apiClient.post(
      "/auth/logout",
      refreshToken ? { refresh_token: refreshToken } : undefined,
      {
        showToastOnError: false,
        showToastOnSuccess: false,
      }
    )
  } catch (error) {
    // Si falla la red o el token ya estaba revocado, procedemos con la purga local igualmente
    console.warn("Fallo o advertencia al revocar sesión en servidor:", error)
  } finally {
    useAuthStore.getState().logout()
    toast.success("Sesión cerrada", {
      description: "Tu sesión ha sido finalizada de forma segura.",
    })
  }
}

/**
 * Renueva manualmente el token de sesión (POST /api/auth/refresh).
 */
export async function refreshSession(): Promise<TokenRefreshResponseDto> {
  const refreshToken = useAuthStore.getState().refreshToken
  if (!refreshToken) {
    throw new Error("No hay un refresh token disponible en almacenamiento.")
  }

  const response = await apiClient.post<TokenRefreshResponseDto>(
    "/auth/refresh",
    { refresh_token: refreshToken },
    {
      showToastOnError: true,
      showToastOnSuccess: false,
    }
  )

  const tokenData = response.data
  useAuthStore.getState().setTokens(tokenData.access_token, tokenData.refresh_token)
  return tokenData
}

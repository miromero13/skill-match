import { apiClient } from "@/services/api-client"

export interface AdminUser {
  id: string
  email: string
  full_name: string
  role: "ADMIN"
  is_active: boolean
  is_locked: boolean
  avatar_url?: string | null
  created_at?: string
  updated_at?: string
}

export interface CreateAdminPayload {
  email: string
  full_name: string
  password: string
}

export interface UpdateAdminPayload {
  full_name: string
}

export interface UpdateAdminPasswordPayload {
  password: string
}

export interface UpdateAdminStatusPayload {
  is_active: boolean
  reason?: string
}

/**
 * Obtiene la lista completa de administradores y el total registrado (GET /api/admin).
 */
export async function getAdministrators(): Promise<{ items: AdminUser[]; count: number }> {
  const response = await apiClient.get<AdminUser[]>("/admin", {
    showToastOnError: true,
    showToastOnSuccess: false,
  })

  return {
    items: response.data || [],
    count: response.count ?? (response.data ? response.data.length : 0),
  }
}

/**
 * Registra un nuevo administrador institucional con contraseña robusta (POST /api/admin).
 * Muestra el toast con el message textual devuelto por el backend (HU-10).
 */
export async function createAdministrator(payload: CreateAdminPayload): Promise<AdminUser> {
  const response = await apiClient.post<AdminUser>("/admin", payload, {
    showToastOnError: true,
    showToastOnSuccess: true,
  })

  return response.data
}

/** Obtiene el detalle de una cuenta administrativa. */
export async function getAdministrator(adminId: string): Promise<AdminUser> {
  const response = await apiClient.get<AdminUser>(`/admin/${adminId}`, {
    showToastOnError: true,
  })
  return response.data
}

/** Edita los datos de una cuenta administrativa. */
export async function updateAdministrator(
  adminId: string,
  payload: UpdateAdminPayload
): Promise<AdminUser> {
  const response = await apiClient.patch<AdminUser>(`/admin/${adminId}`, payload, {
    showToastOnError: true,
    showToastOnSuccess: true,
  })
  return response.data
}

/** Cambia la contraseña sin invalidar sesiones existentes. */
export async function updateAdministratorPassword(
  adminId: string,
  payload: UpdateAdminPasswordPayload
): Promise<AdminUser> {
  const response = await apiClient.patch<AdminUser>(`/admin/${adminId}/password`, payload, {
    showToastOnError: true,
    showToastOnSuccess: true,
  })
  return response.data
}

/**
 * Suspende o reactiva una cuenta de administrador (PATCH /api/admin/{id}/status).
 * Muestra el toast con el message textual devuelto por el backend (HU-10).
 */
export async function updateAdministratorStatus(
  adminId: string,
  payload: UpdateAdminStatusPayload
): Promise<AdminUser> {
  const response = await apiClient.patch<AdminUser>(`/admin/${adminId}/status`, payload, {
    showToastOnError: true,
    showToastOnSuccess: true,
  })

  return response.data
}

// Tipado estándar del sobre de respuesta de la API de SkillMatch
// Sincronizado estrictamente con el contrato del backend:
// { "statuscode": number, "message": string, "data": T, "count": number | null }

export interface APIResponse<T = unknown> {
  statuscode: number
  message: string
  data: T
  count?: number | null
  // Propiedades opcionales para retrocompatibilidad
  success?: boolean
  errors?: Record<string, string[]> | string[] | null
  timestamp?: string
}

export interface PaginatedData<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

export interface RequestOptions extends Omit<RequestInit, "body"> {
  params?: Record<string, string | number | boolean | undefined>
  showToastOnError?: boolean
  showToastOnSuccess?: boolean
  successMessage?: string
  body?: unknown
}

export class ApiError extends Error {
  statuscode: number
  data?: unknown

  constructor(message: string, statuscode: number, data?: unknown) {
    super(message)
    this.name = "ApiError"
    this.statuscode = statuscode
    this.data = data
  }
}

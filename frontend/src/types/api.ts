// Tipado estándar del sobre de respuesta de la API de SkillMatch
// Sincronizado con el contrato del backend: { statuscode, message, data, count }

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
  status: number
  errors?: Record<string, string[]> | string[] | null

  constructor(message: string, status: number, errors?: Record<string, string[]> | string[] | null) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.errors = errors
  }
}

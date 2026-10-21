// Tipado estándar del sobre de respuesta de la API de SkillMatch

export interface APIResponse<T = unknown> {
  success: boolean
  data: T
  message: string
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

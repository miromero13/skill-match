import { type APIResponse, type RequestOptions, ApiError } from "@/types/api"
import { useAuthStore } from "@/stores/auth-store"
import { toast } from "sonner"

const BASE_URL = import.meta.env.VITE_API_URL || "/api"

class ApiClient {
  private baseUrl: string

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/$/, "")
  }

  private buildUrl(endpoint: string, params?: Record<string, string | number | boolean | undefined>): string {
    const cleanEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`
    const fullUrl = `${this.baseUrl}${cleanEndpoint}`

    if (!params) return fullUrl

    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, String(value))
      }
    })

    const queryString = searchParams.toString()
    return queryString ? `${fullUrl}?${queryString}` : fullUrl
  }

  private async request<T>(endpoint: string, options: RequestOptions = {}): Promise<APIResponse<T>> {
    const {
      params,
      showToastOnError = true,
      showToastOnSuccess = false,
      successMessage,
      headers: customHeaders,
      body,
      ...fetchOptions
    } = options

    const url = this.buildUrl(endpoint, params)

    // 1. Interceptor de Petición: Inyección automática de Headers y Token JWT
    const token = useAuthStore.getState().token
    const headers = new Headers(customHeaders)

    if (!headers.has("Accept")) {
      headers.set("Accept", "application/json")
    }

    if (token && !headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${token}`)
    }

    let serializedBody: BodyInit | undefined = undefined
    if (body !== undefined && body !== null) {
      if (body instanceof FormData) {
        serializedBody = body
        // El navegador asigna el multipart boundary automáticamente
      } else {
        headers.set("Content-Type", "application/json")
        serializedBody = JSON.stringify(body)
      }
    }

    try {
      const response = await fetch(url, {
        ...fetchOptions,
        headers,
        body: serializedBody,
      })

      // 2. Interceptor de Respuesta: Manejo de 401 Unauthorized (Sesión expirada)
      if (response.status === 401) {
        useAuthStore.getState().logout()
        toast.error("Sesión expirada", {
          description: "Por favor, iniciá sesión nuevamente para continuar.",
        })
        throw new ApiError("No autorizado o sesión expirada", 401)
      }

      let jsonResponse: APIResponse<T>
      const contentType = response.headers.get("content-type")
      if (contentType && contentType.includes("application/json")) {
        jsonResponse = await response.json()
      } else {
        const text = await response.text()
        jsonResponse = {
          statuscode: response.status,
          success: response.ok,
          data: text as unknown as T,
          message: response.statusText,
        }
      }

      // 3. Manejo de errores HTTP o de lógica de negocio (statuscode >= 400)
      const isSuccess = response.ok && (jsonResponse.statuscode ? jsonResponse.statuscode < 400 : jsonResponse.success !== false)
      if (!isSuccess) {
        const errorMessage =
          jsonResponse.message || `Error del servidor (Código ${response.status})`

        if (showToastOnError) {
          toast.error("Error en la solicitud", {
            description: errorMessage,
          })
        }

        throw new ApiError(errorMessage, response.status, jsonResponse.errors)
      }

      // 4. Notificación automática de éxito si se solicitó
      if (showToastOnSuccess || successMessage) {
        toast.success(successMessage || jsonResponse.message || "Operación exitosa")
      }

      return jsonResponse
    } catch (error) {
      if (error instanceof ApiError) {
        throw error
      }

      // Errores de red, DNS o conexión rechazada
      const networkErrorMessage =
        error instanceof Error ? error.message : "Error de conexión con el servidor"

      if (showToastOnError) {
        toast.error("Error de Red", {
          description: "No se pudo establecer comunicación con el backend de SkillMatch.",
        })
      }

      throw new ApiError(networkErrorMessage, 0)
    }
  }

  // Métodos HTTP semánticos
  public get<T>(endpoint: string, options?: RequestOptions): Promise<APIResponse<T>> {
    return this.request<T>(endpoint, { ...options, method: "GET" })
  }

  public post<T>(endpoint: string, body?: unknown, options?: RequestOptions): Promise<APIResponse<T>> {
    return this.request<T>(endpoint, { ...options, method: "POST", body })
  }

  public put<T>(endpoint: string, body?: unknown, options?: RequestOptions): Promise<APIResponse<T>> {
    return this.request<T>(endpoint, { ...options, method: "PUT", body })
  }

  public patch<T>(endpoint: string, body?: unknown, options?: RequestOptions): Promise<APIResponse<T>> {
    return this.request<T>(endpoint, { ...options, method: "PATCH", body })
  }

  public delete<T>(endpoint: string, options?: RequestOptions): Promise<APIResponse<T>> {
    return this.request<T>(endpoint, { ...options, method: "DELETE" })
  }
}

export const apiClient = new ApiClient(BASE_URL)

import { type APIResponse, type RequestOptions, ApiError } from "@/types/api"
import { useAuthStore } from "@/stores/auth-store"
import { toast } from "sonner"

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api"

class ApiClient {
  private baseUrl: string
  private isRefreshing = false
  private refreshSubscribers: Array<{
    resolve: (token: string) => void
    reject: (error: unknown) => void
  }> = []

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/$/, "")
  }

  private onTokenRefreshed(newToken: string) {
    this.refreshSubscribers.forEach((sub) => sub.resolve(newToken))
    this.refreshSubscribers = []
  }

  private onTokenRefreshFailed(error: unknown) {
    this.refreshSubscribers.forEach((sub) => sub.reject(error))
    this.refreshSubscribers = []
  }

  private async performTokenRefresh(): Promise<string> {
    const currentRefreshToken = useAuthStore.getState().refreshToken

    if (!currentRefreshToken) {
      throw new Error("No refresh token available")
    }

    const refreshUrl = `${this.baseUrl}/auth/refresh`
    const response = await fetch(refreshUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ refresh_token: currentRefreshToken }),
    })

    if (!response.ok) {
      throw new Error("Failed to refresh token from server")
    }

    const json = (await response.json()) as APIResponse<{
      access_token: string
      refresh_token: string
      token_type: string
      expires_in: number
    }>

    if (!json.data || !json.data.access_token) {
      throw new Error("Invalid token refresh response payload")
    }

    const { access_token, refresh_token } = json.data
    useAuthStore.getState().setTokens(access_token, refresh_token)
    return access_token
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

  private async request<T>(
    endpoint: string,
    options: RequestOptions = {},
    isRetry = false
  ): Promise<APIResponse<T>> {
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

    // 1. Inyección de Headers y Token JWT
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

      // 2. Interceptor de 401 Unauthorized (Auto-refresh con cola concurrente)
      if (
        response.status === 401 &&
        !isRetry &&
        !endpoint.includes("/auth/login") &&
        !endpoint.includes("/auth/refresh")
      ) {
        const { refreshToken } = useAuthStore.getState()
        if (refreshToken) {
          try {
            let newToken: string
            if (this.isRefreshing) {
              newToken = await new Promise<string>((resolve, reject) => {
                this.refreshSubscribers.push({ resolve, reject })
              })
            } else {
              this.isRefreshing = true
              try {
                newToken = await this.performTokenRefresh()
                this.onTokenRefreshed(newToken)
              } catch (refreshErr) {
                this.onTokenRefreshFailed(refreshErr)
                throw refreshErr
              } finally {
                this.isRefreshing = false
              }
            }

            // Reintentar la solicitud original con el nuevo Access Token
            const retryHeaders = new Headers(customHeaders)
            retryHeaders.set("Authorization", `Bearer ${newToken}`)

            return await this.request<T>(
              endpoint,
              {
                ...options,
                headers: retryHeaders,
              },
              true
            )
          } catch (refreshError) {
            console.warn("Fallo crítico durante el auto-refresh de tokens:", refreshError)
            useAuthStore.getState().logout()
            toast.error("Sesión expirada", {
              description: "Por favor, iniciá sesión nuevamente para continuar.",
            })
            throw new ApiError("No autorizado o sesión expirada", 401)
          }
        } else {
          useAuthStore.getState().logout()
          toast.error("Sesión expirada", {
            description: "Por favor, iniciá sesión nuevamente para continuar.",
          })
          throw new ApiError("No autorizado o sesión expirada", 401)
        }
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

      // 3. Manejo estándar de errores bajo el contrato APIResponse (statuscode >= 400)
      const isSuccess = response.ok && (jsonResponse.statuscode ? jsonResponse.statuscode < 400 : jsonResponse.success !== false)
      if (!isSuccess) {
        const errorMessage =
          jsonResponse.message || `Error en la solicitud (Código ${response.status})`

        if (showToastOnError) {
          toast.error(errorMessage)
        }

        throw new ApiError(errorMessage, response.status, jsonResponse.data)
      }

      // 4. Notificación de éxito si se solicitó (muestra textualmente el message del backend - HU-10)
      if (showToastOnSuccess || successMessage) {
        toast.success(jsonResponse.message || successMessage || "Operación exitosa")
      }

      return jsonResponse
    } catch (error) {
      if (error instanceof ApiError) {
        throw error
      }

      // Errores de red o conexión
      const networkErrorMessage =
        error instanceof Error ? error.message : "Error de comunicación con el servidor"

      if (showToastOnError) {
        toast.error("Error de Red", {
          description: "No se pudo establecer conexión con el backend de SkillMatch.",
        })
      }

      throw new ApiError(networkErrorMessage, 0)
    }
  }

  // Métodos HTTP semánticos
  // Soportan tanto: apiClient.post("/url", body, options)
  // Como la sobrecarga directa: apiClient.post("/url", { body, ...options })
  public get<T>(endpoint: string, options?: RequestOptions): Promise<APIResponse<T>> {
    return this.request<T>(endpoint, { ...options, method: "GET" })
  }

  public post<T>(endpoint: string, bodyOrOptions?: unknown, options?: RequestOptions): Promise<APIResponse<T>> {
    if (options !== undefined) {
      return this.request<T>(endpoint, { ...options, method: "POST", body: bodyOrOptions })
    }
    // Si solo viene un argumento y tiene estructura de RequestOptions con body explícito
    if (bodyOrOptions && typeof bodyOrOptions === "object" && "body" in bodyOrOptions) {
      const opts = bodyOrOptions as RequestOptions
      return this.request<T>(endpoint, { ...opts, method: "POST" })
    }
    return this.request<T>(endpoint, { method: "POST", body: bodyOrOptions })
  }

  public put<T>(endpoint: string, bodyOrOptions?: unknown, options?: RequestOptions): Promise<APIResponse<T>> {
    if (options !== undefined) {
      return this.request<T>(endpoint, { ...options, method: "PUT", body: bodyOrOptions })
    }
    if (bodyOrOptions && typeof bodyOrOptions === "object" && "body" in bodyOrOptions) {
      const opts = bodyOrOptions as RequestOptions
      return this.request<T>(endpoint, { ...opts, method: "PUT" })
    }
    return this.request<T>(endpoint, { method: "PUT", body: bodyOrOptions })
  }

  public patch<T>(endpoint: string, bodyOrOptions?: unknown, options?: RequestOptions): Promise<APIResponse<T>> {
    if (options !== undefined) {
      return this.request<T>(endpoint, { ...options, method: "PATCH", body: bodyOrOptions })
    }
    if (bodyOrOptions && typeof bodyOrOptions === "object" && "body" in bodyOrOptions) {
      const opts = bodyOrOptions as RequestOptions
      return this.request<T>(endpoint, { ...opts, method: "PATCH" })
    }
    return this.request<T>(endpoint, { method: "PATCH", body: bodyOrOptions })
  }

  public delete<T>(endpoint: string, options?: RequestOptions): Promise<APIResponse<T>> {
    return this.request<T>(endpoint, { ...options, method: "DELETE" })
  }
}

export const apiClient = new ApiClient(BASE_URL)

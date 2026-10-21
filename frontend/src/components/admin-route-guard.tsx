import type { ReactNode } from "react"
import { Navigate } from "react-router-dom"
import { useAuthStore } from "@/stores/auth-store"
import { NotFoundPage } from "@/pages/not-found-page"

interface AdminRouteGuardProps {
  children: ReactNode
}

/**
 * Guardia de ruta para vistas administrativas exclusivas (/admin/*).
 * POLÍTICA DE SEGURIDAD POR OFUSCACIÓN (HU-08 / RF-USR-10):
 * - Si no está autenticado: redirige a /admin/login.
 * - Si está autenticado pero su rol NO es "ADMIN" (ej. es un "MEMBER"):
 *   Renderiza inmediatamente la pantalla 404 Not Found (nunca 403 Forbidden).
 *   Esto previene que miembros comunes sospechen o descubran la existencia del panel administrativo.
 */
export function AdminRouteGuard({ children }: AdminRouteGuardProps) {
  const { isAuthenticated, user, token } = useAuthStore()

  if (!isAuthenticated || !token) {
    return <Navigate to="/admin/login" replace />
  }

  if (user?.role !== "ADMIN") {
    return <NotFoundPage />
  }

  return <>{children}</>
}

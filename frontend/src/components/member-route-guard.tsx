import type { ReactNode } from "react"
import { Navigate, useLocation } from "react-router-dom"
import { useAuthStore } from "@/stores/auth-store"

interface MemberRouteGuardProps {
  children: ReactNode
}

/**
 * Guardia de ruta para la plataforma de miembros (/app/*).
 * Criterios de aceptación (HU-07 / HU-09):
 * - Si no está autenticado o no hay token: Redirige a /login conservando la ruta previa.
 * - Si está autenticado como ADMIN: Lo redirige a su panel correspondiente (/admin/dashboard).
 * - Si está autenticado con rol MEMBER: Da acceso al árbol de componentes.
 */
export function MemberRouteGuard({ children }: MemberRouteGuardProps) {
  const { isAuthenticated, user, token } = useAuthStore()
  const location = useLocation()

  if (!isAuthenticated || !token) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (user?.role === "ADMIN") {
    return <Navigate to="/admin/dashboard" replace />
  }

  return <>{children}</>
}

import type { ReactNode } from "react"
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

  // POLÍTICA DE SEGURIDAD POR OFUSCACIÓN (RF-SEC-01 / HU-10):
  // Si el usuario no está autenticado, no tiene token o su rol NO es "ADMIN" (ej. es un "MEMBER" o anónimo):
  // Renderiza OBLIGATORIAMENTE la pantalla 404 Not Found (nunca redirige a /admin/login ni 403 Forbidden).
  // Esto previene que visitantes o miembros descubran la existencia o rutas del panel administrativo.
  if (!isAuthenticated || !token || user?.role !== "ADMIN") {
    return <NotFoundPage />
  }

  return <>{children}</>
}

import { Navigate, useLocation } from "react-router-dom"
import { getAuthSessionVersion, useAuthStore } from "@/stores/auth-store"
import { PlatformLayout } from "@/layouts/platform-layout"
import { AdminLayout } from "@/layouts/admin-layout"

/** Personal routes shared by both roles, without opening /app to administrators. */
export function NotificationLayout() {
  const { user, token, isAuthenticated } = useAuthStore()
  const version = getAuthSessionVersion()
  const location = useLocation()
  if (!isAuthenticated || !token || !user)
    return <Navigate to="/login" state={{ from: location }} replace />
  return user.role === "ADMIN" ? (
    <AdminLayout key={version} />
  ) : (
    <PlatformLayout key={version} />
  )
}

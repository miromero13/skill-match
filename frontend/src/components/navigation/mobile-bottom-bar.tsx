import { useEffect } from "react"
import { Link, useLocation } from "react-router-dom"
import { Home, Compass, CalendarDays, Bell, User } from "lucide-react"
import { useNotificationStore } from "@/stores/notification-store"

export function MobileBottomBar() {
  const location = useLocation()
  const path = location.pathname
  const unreadTotal = useNotificationStore((s) => s.unreadTotal)

  useEffect(() => {
    void useNotificationStore.getState().loadUnread()
  }, [])

  const items = [
    { label: "Inicio", icon: Home, to: "/app", active: path === "/app" },
    { label: "Buscar", icon: Compass, to: "/app/search", active: path.startsWith("/app/search") },
    { label: "Sesiones", icon: CalendarDays, to: "/app/sessions", active: path.startsWith("/app/sessions") || path.startsWith("/app/swaps") },
    { label: "Avisos", icon: Bell, to: "/notifications", active: path.startsWith("/notifications"), badge: unreadTotal },
    { label: "Perfil", icon: User, to: "/app/profile", active: path.startsWith("/app/profile") },
  ]

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 flex h-[calc(54px+env(safe-area-inset-bottom,0px))] pb-[env(safe-area-inset-bottom,0px)] items-center justify-around border-t bg-background/95 backdrop-blur-md px-2 supports-[backdrop-filter]:bg-background/80">
      {items.map((item) => {
        const Icon = item.icon
        return (
          <Link
            key={item.to}
            to={item.to}
            className={`relative flex flex-col items-center justify-center gap-0.5 w-14 py-1 text-[10px] font-medium transition-colors ${
              item.active
                ? "text-primary font-bold"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <div className="relative">
              <Icon className="h-5 w-5" />
              {item.badge !== undefined && item.badge > 0 && (
                <span className="absolute -top-1 -right-2 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[9px] font-bold text-destructive-foreground shadow-xs animate-in zoom-in-75">
                  {item.badge > 99 ? "99+" : item.badge}
                </span>
              )}
            </div>
            <span>{item.label}</span>
          </Link>
        )
      })}
    </nav>
  )
}

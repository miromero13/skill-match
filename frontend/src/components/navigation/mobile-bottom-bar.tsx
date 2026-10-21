import { Link, useLocation } from "react-router-dom"
import { Home, Compass, ArrowLeftRight, Bell, User } from "lucide-react"

export function MobileBottomBar() {
  const location = useLocation()
  const path = location.pathname

  const items = [
    { label: "Inicio", icon: Home, to: "/app", active: path === "/app" },
    { label: "Buscar", icon: Compass, to: "/app/search", active: path.startsWith("/app/search") },
    { label: "Swaps", icon: ArrowLeftRight, to: "/app/swaps", active: path.startsWith("/app/swaps") },
    { label: "Avisos", icon: Bell, to: "/app/notifications", active: path.startsWith("/app/notifications") },
    { label: "Perfil", icon: User, to: "/app/profile", active: path.startsWith("/app/profile") },
  ]

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 flex h-[54px] items-center justify-around border-t bg-background/95 backdrop-blur-md px-2 supports-[backdrop-filter]:bg-background/80">
      {items.map((item) => {
        const Icon = item.icon
        return (
          <Link
            key={item.to}
            to={item.to}
            className={`flex flex-col items-center justify-center gap-0.5 w-14 py-1 text-[10px] font-medium transition-colors ${
              item.active
                ? "text-primary font-bold"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Icon className="h-5 w-5" />
            <span>{item.label}</span>
          </Link>
        )
      })}
    </nav>
  )
}

import { Link, useLocation } from "react-router-dom"
import {
  User,
  ArrowLeftRight,
  Wallet,
  Calendar,
  Award,
  Star,
  AlertTriangle,
  ShieldCheck,
} from "lucide-react"

export function PlatformSidebar() {
  const location = useLocation()
  const path = location.pathname

  const menuItems = [
    { label: "Mi Perfil", icon: User, to: "/app/profile", active: path === "/app/profile" || path === "/app" },
    { label: "Intercambios Activos", icon: ArrowLeftRight, to: "/app/swaps", active: path === "/app/swaps", badge: "2" },
    { label: "Billetera & Cashout", icon: Wallet, to: "/app/wallet", active: path === "/app/wallet", value: "150 pts" },
    { label: "Disponibilidad y Horarios", icon: Calendar, to: "/app/availability", active: path === "/app/availability" },
    { label: "Certificados de IA", icon: Award, to: "/app/certificates", active: path === "/app/certificates" },
    { label: "Reputación y Reseñas", icon: Star, to: "/app/reputation", active: path === "/app/reputation", value: "4.9 ★" },
    { label: "Centro de Quejas", icon: AlertTriangle, to: "/app/complaints", active: path === "/app/complaints" },
  ]

  const shortcuts = [
    { name: "Sofía Rossi", tag: "Guitarra", initials: "SR" },
    { name: "Mateo Fernández", tag: "Python", initials: "MF" },
    { name: "Comunidad Python", tag: "Grupo", initials: "CP" },
  ]

  return (
    <aside className="w-64 shrink-0 space-y-4 p-4 text-sm hidden lg:block">
      {/* 1. Mini User Card */}
      <div className="flex items-center gap-3 rounded-xl border bg-card p-3 shadow-2xs">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary text-primary-foreground font-black text-xs shrink-0">
          CM
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1">
            <span className="font-bold text-xs text-foreground truncate">Carlos Méndez</span>
            <ShieldCheck className="h-3.5 w-3.5 text-primary shrink-0" />
          </div>
          <span className="text-[11px] text-muted-foreground block truncate">@carlos.dev</span>
        </div>
      </div>

      {/* 2. Navigation Menu */}
      <nav className="space-y-0.5">
        {menuItems.map((item) => {
          const Icon = item.icon
          const isActive = item.active
          return (
            <Link
              key={item.to}
              to={item.to}
              className={`flex items-center justify-between rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                isActive
                  ? "bg-primary/10 text-primary font-bold"
                  : "text-foreground/80 hover:bg-muted/70 hover:text-foreground"
              }`}
            >
              <div className="flex items-center gap-3">
                <Icon className={`h-4 w-4 ${isActive ? "text-primary" : "text-muted-foreground"}`} />
                <span>{item.label}</span>
              </div>
              {item.badge && (
                <span className="rounded-full bg-primary/15 px-2 py-0.5 text-[10px] font-bold text-primary">
                  {item.badge}
                </span>
              )}
              {item.value && (
                <span className="text-[11px] font-semibold text-primary">
                  {item.value}
                </span>
              )}
            </Link>
          )
        })}
      </nav>

      {/* 3. Shortcuts */}
      <div className="pt-2 space-y-2 border-t">
        <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground px-3 block">
          ACCESOS DIRECTOS
        </span>
        <div className="space-y-1">
          {shortcuts.map((sc) => (
            <div
              key={sc.name}
              className="flex items-center justify-between rounded-lg px-3 py-1.5 text-xs text-foreground/80 hover:bg-muted/50 cursor-pointer transition-colors"
            >
              <div className="flex items-center gap-2.5">
                <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/15 text-primary text-[10px] font-bold">
                  {sc.initials}
                </div>
                <span className="text-xs font-medium truncate">{sc.name}</span>
              </div>
              <span className="text-[10px] text-muted-foreground">{sc.tag}</span>
            </div>
          ))}
        </div>
      </div>
    </aside>
  )
}

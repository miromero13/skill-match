import { Link, useLocation } from "react-router-dom"
import { useAuthStore } from "@/stores/auth-store"
import {
  User,
  Compass,
  ArrowLeftRight,
  Handshake,
  Wallet,
  Calendar,
  Award,
  BookOpen,
  Star,
  AlertTriangle,
  ShieldCheck,
  Shield,
} from "lucide-react"

export function PlatformSidebar() {
  const location = useLocation()
  const path = location.pathname
  const { user } = useAuthStore()

  const menuItems: Array<{
    label: string
    icon: React.ComponentType<{ className?: string }>
    to: string
    active: boolean
    badge?: string
    value?: string
  }> = [
    {
      label: "Mis Coincidencias",
      icon: Handshake,
      to: "/matches",
      active: path === "/matches",
    },
    {
      label: "Mi Perfil y Horarios",
      icon: User,
      to: "/app/profile",
      active: path === "/app/profile" || path === "/app",
    },
    {
      label: "Explorar Instructores",
      icon: Compass,
      to: "/app/search",
      active: path.startsWith("/app/search") || path === "/search",
    },
    {
      label: "Habilidades que enseño",
      icon: BookOpen,
      to: "/app/teaching-skills",
      active: path === "/app/teaching-skills",
    },
    {
      label: "Quiero Aprender",
      icon: BookOpen,
      to: "/app/learning-skills",
      active: path === "/app/learning-skills",
    },
    {
      label: "Mis Sesiones",
      icon: Calendar,
      to: "/app/sessions",
      active: path === "/app/sessions" || path === "/app/swaps",
    },
    {
      label: "Intercambios Activos",
      icon: ArrowLeftRight,
      to: "/app/swaps",
      active: path === "/app/swaps",
    },
    {
      label: "Billetera",
      icon: Wallet,
      to: "/app/wallet",
      active: path === "/app/wallet",
      value: `${user?.skillPointsBalance ?? 0} pts`,
    },
    {
      label: "Disponibilidad y Agenda",
      icon: Calendar,
      to: "/app/availability",
      active: path === "/app/availability",
    },
    {
      label: "Certificados de IA",
      icon: Award,
      to: "/app/certificates",
      active: path === "/app/certificates",
    },
    {
      label: "Reputación y Reseñas",
      icon: Star,
      to: "/app/reputation",
      active: path === "/app/reputation",
    },
    {
      label: "Centro de Quejas",
      icon: AlertTriangle,
      to: "/app/complaints",
      active: path === "/app/complaints",
    },
  ]

  const shortcuts = [
    { name: "Buscar Instructores", tag: "Catálogo", to: "/app/search" },
    { name: "Mis Coincidencias", tag: "Intercambio", to: "/matches" },
    { name: "Mis Habilidades", tag: "Perfil", to: "/app/teaching-skills" },
  ]

  return (
    <aside className="hidden h-full w-64 shrink-0 space-y-4 overflow-y-auto border-r border-border bg-card/30 p-4 text-sm lg:block">
      {/* 1. Mini User Card */}
      <div className="flex items-center gap-3 rounded-xl border bg-card p-3 shadow-2xs">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-black text-primary-foreground">
          {user?.fullName
            .split(" ")
            .map((name) => name[0])
            .join("")
            .slice(0, 2)
            .toUpperCase() || "MB"}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1">
            <span className="truncate text-xs font-bold text-foreground">
              {user?.fullName || "Miembro"}
            </span>
            <ShieldCheck className="h-3.5 w-3.5 shrink-0 text-primary" />
          </div>
          <span className="block truncate text-[11px] text-muted-foreground">
            {user?.email}
          </span>
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
                  ? "bg-primary/10 font-bold text-primary"
                  : "text-foreground/80 hover:bg-muted/70 hover:text-foreground"
              }`}
            >
              <div className="flex items-center gap-3">
                <Icon
                  className={`h-4 w-4 ${isActive ? "text-primary" : "text-muted-foreground"}`}
                />
                <span>{item.label}</span>
              </div>
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
      <div className="space-y-2 border-t pt-2">
        <span className="block px-3 text-[10px] font-bold tracking-wider text-muted-foreground uppercase">
          ACCESOS DIRECTOS
        </span>
        <div className="space-y-1">
          {shortcuts.map((sc) => (
            <Link
              key={sc.name}
              to={sc.to}
              className="flex cursor-pointer items-center justify-between rounded-lg px-3 py-1.5 text-xs text-foreground/80 transition-colors hover:bg-muted/50"
            >
              <span className="truncate text-xs font-medium">{sc.name}</span>
              <span className="text-[10px] text-muted-foreground">
                {sc.tag}
              </span>
            </Link>
          ))}
        </div>
      </div>

      {/* 4. Restricción en Sidebar: 'Equipo Administrador' solo visible para UserRole.ADMIN (HU-10) */}
      {user?.role === "ADMIN" && (
        <div className="space-y-2 border-t pt-2">
          <span className="block px-3 text-[10px] font-bold tracking-wider text-primary uppercase">
            EQUIPO ADMINISTRADOR
          </span>
          <Link
            to="/admin/administrators"
            className="flex items-center gap-3 rounded-lg px-3 py-2 text-xs font-semibold text-primary transition-colors hover:bg-primary/10"
          >
            <Shield className="h-4 w-4 text-primary" />
            <span>Gestión de Administradores</span>
          </Link>
        </div>
      )}
    </aside>
  )
}

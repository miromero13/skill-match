import { NotificationBell } from "@/components/notifications/notification-bell"
import { Button } from "@/components/ui/button"
import { useState } from "react"
import { Outlet, NavLink, useNavigate, useLocation } from "react-router-dom"
import { useAuthStore } from "@/stores/auth-store"
import { logoutSession } from "@/services/auth-service"
import {
  LayoutDashboard,
  Users,
  BookOpen,
  ShieldAlert,
  Scale,
  Brain,
  Video,
  Menu,
  X,
  LogOut,
  Loader2,
  Circle,
} from "lucide-react"

export function AdminLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user } = useAuthStore()
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)
  const [isLoggingOut, setIsLoggingOut] = useState(false)

  const handleLogout = async () => {
    setIsLoggingOut(true)
    try {
      await logoutSession()
    } finally {
      setIsLoggingOut(false)
      navigate("/admin/login", { replace: true })
    }
  }

  // Menú con restricción RBAC: 'Gestión de Usuarios' (Equipo Administrador) solo visible para rol ADMIN (HU-10 / Vista 15A)
  const navItems = [
    {
      label: "Dashboard & Analítica",
      to: "/admin/dashboard",
      icon: LayoutDashboard,
      visible: true,
    },
    {
      label: "Gestión de Usuarios",
      to: "/admin/administrators",
      icon: Users,
      visible: user?.role === "ADMIN", // Restricción estricta RBAC (HU-10)
    },
    {
      label: "Catálogo de Habilidades",
      to: "/admin/catalog",
      icon: BookOpen,
      visible: true,
    },
    {
      label: "Auditoría de Fraude",
      to: "/admin/fraud-audit",
      icon: ShieldAlert,
      visible: true,
    },
    {
      label: "Disputas & Quejas",
      to: "/admin/disputes",
      icon: Scale,
      visible: true,
    },
    {
      label: "Captura de Datasets",
      to: "/admin/capture",
      icon: Video,
      visible: user?.role === "ADMIN", // Restricción estricta RBAC (HU-17 / RF-IA-18)
    },
    {
      label: "IA & Datasets",
      to: "/admin/ai-datasets",
      icon: Brain,
      visible: true,
    },
  ].filter((item) => item.visible)

  // Iniciales del Administrador para el Avatar
  const getInitials = (name?: string) => {
    if (!name) return "AD"
    const parts = name.trim().split(" ")
    if (parts.length >= 2) {
      return `${parts[0][0]}${parts[1][0]}`.toUpperCase()
    }
    return name.slice(0, 2).toUpperCase()
  }

  // Título dinámico para el breadcrumb de la barra superior
  const getBreadcrumbTitle = () => {
    if (location.pathname.includes("/admin/dashboard")) {
      return "Dashboard & Analítica"
    }
    if (location.pathname.includes("/admin/administrators")) {
      return "Directorio de Miembros & Control de Acceso"
    }
    if (location.pathname.includes("/admin/catalog") || location.pathname.includes("/admin/skills")) {
      return "Catálogo Maestro de Habilidades"
    }
    if (location.pathname.includes("/admin/capture") || location.pathname.includes("/admin/ai-datasets")) {
      return "Ingesta y Captura de Muestras Multimedia"
    }
    return "Panel Central de Control"
  }

  return (
    <div className="h-screen w-full flex overflow-hidden bg-[#0F1416] text-[#F0FDFA] dark">
      {/* 1. SIDEBAR DESKTOP (Fijo en el lateral izquierdo, no se desplaza con el scroll del contenido) */}
      <aside className="hidden lg:flex flex-col w-[260px] h-full bg-[#0F1416] text-[#FFFFFF] border-r border-[#1E2629] shrink-0 justify-between p-[20px_16px] overflow-y-auto">
        <div className="flex flex-col gap-5">
          {/* BrandRow (n6742) */}
          <div className="flex items-center gap-2.5">
            <div className="w-[34px] h-[34px] rounded-[8px] bg-[#00786F] flex items-center justify-center font-extrabold text-white text-sm shadow-xs shrink-0">
              SM
            </div>
            <div className="flex flex-col gap-0.5 min-w-0">
              <div className="font-extrabold text-[13px] tracking-wide text-white leading-tight">SkillMatch Admin</div>
              <div className="text-[9px] font-medium text-[#67787C] leading-none">Sistema de Información v2.4</div>
            </div>
          </div>

          {/* MenuList (n6748: gap: 4px) */}
          <nav className="flex flex-col gap-1">
            {navItems.map((item) => {
              const Icon = item.icon
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `h-[38px] px-3 rounded-[6px] flex items-center gap-2.5 text-[12px] transition-colors ${
                      isActive
                        ? "bg-[#00786F] text-white font-bold shadow-xs"
                        : "text-[#67787C] hover:text-white hover:bg-[#1A2225] font-medium"
                    }`
                  }
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  <span>{item.label}</span>
                </NavLink>
              )
            })}
          </nav>
        </div>

        {/* AdminUserBox (OpenPencil n6767: padding: 10px, cornerRadius: 8px, fill: #1A2225) */}
        <div className="p-2.5 rounded-[8px] bg-[#1A2225] flex items-center justify-between gap-2.5">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-8 h-8 rounded-full bg-[#00786F] text-[#F0FDFA] flex items-center justify-center text-[11px] font-extrabold shrink-0">
              {getInitials(user?.fullName)}
            </div>
            <div className="flex flex-col gap-0.5 min-w-0">
              <p className="text-[11px] font-bold text-white truncate leading-tight">
                {user?.fullName || "Administrador Central"}
              </p>
              <p className="text-[9px] font-medium text-[#00786F] leading-none">
                Rol: ADMIN
              </p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            disabled={isLoggingOut}
            title="Cerrar Sesión"
            className="p-1 rounded text-[#67787C] hover:text-white hover:bg-red-500/10 transition-colors cursor-pointer"
          >
            {isLoggingOut ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin text-[#00786F]" />
            ) : (
              <LogOut className="w-3.5 h-3.5" />
            )}
          </button>
        </div>
      </aside>

      {/* 2. CONTENIDO PRINCIPAL Y TOPBAR (Área con scroll vertical independiente) */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-y-auto bg-[#0F1416]">
        {/* Admin_Topbar (Sticky en la parte superior del contenido) */}
        <header className="h-[54px] shrink-0 px-4 sm:px-6 bg-[#0F1416] border-b border-[#1E2629] flex items-center justify-between sticky top-0 z-30 shadow-2xs">
          {/* Izquierda: Hamburguesa en mobile + Breadcrumb */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className="lg:hidden p-1.5 rounded-md text-[#8B9D9F] hover:text-white hover:bg-[#1A2225] cursor-pointer"
              aria-label="Abrir Menú"
            >
              {isMobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
            <div className="text-[12px] font-semibold text-[#8B9D9F]">
              <span className="hidden sm:inline">Consola de Administración / </span>
              <span className="text-[#F0FDFA] font-bold">{getBreadcrumbTitle()}</span>
            </div>
          </div>

          {/* Derecha: Badge de Estado del Sistema */}
          <div className="flex items-center gap-2">
            <NotificationBell />
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#00786F1A] text-[#2DD4BF] text-[11px] font-semibold border border-[#00786F40]">
              <Circle className="w-2 h-2 fill-[#2DD4BF] text-[#2DD4BF] animate-pulse" />
              <span className="hidden sm:inline">Sistema En Línea · Latencia 24ms</span>
              <span className="sm:hidden">En Línea</span>
            </div>
          </div>
        </header>

        {/* 3. MENU MÓVIL DESPLEGABLE (17A) */}
        {isMobileMenuOpen && (
          <div className="lg:hidden bg-[#0B1011] text-white p-4 border-b border-[#1B2426] space-y-2 z-40">
            {navItems.map((item) => {
              const Icon = item.icon
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={() => setIsMobileMenuOpen(false)}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-semibold ${
                      isActive ? "bg-[#00786F] text-white" : "text-[#8B9D9F] hover:bg-[#141C1E]"
                    }`
                  }
                >
                  <Icon className="w-4 h-4" />
                  <span>{item.label}</span>
                </NavLink>
              )
            })}
            <div className="pt-3 border-t border-[#1B2426] flex items-center justify-between">
              <span className="text-xs text-[#8B9D9F]">{user?.email}</span>
              <button
                onClick={handleLogout}
                className="text-xs text-red-400 font-semibold flex items-center gap-1"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span>Salir</span>
              </button>
            </div>
          </div>
        )}

        {/* 4. ÁREA DE PÁGINAS HIJAS */}
        <main className="flex-1 p-4 pb-24 sm:p-6 sm:pb-24 lg:p-8">
          <Outlet />
        </main>
        <nav aria-label="Navegación móvil de administración" className="fixed inset-x-0 bottom-0 z-40 flex flex-wrap justify-around gap-1 border-t bg-background p-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] text-foreground lg:hidden">
          <Button asChild variant="ghost"><NavLink to="/admin/dashboard">Panel</NavLink></Button>
          <Button asChild variant="ghost"><NavLink to="/notifications" end>Mis avisos</NavLink></Button>
          <Button asChild variant="ghost"><NavLink to="/notifications/settings">Preferencias</NavLink></Button>
        </nav>
      </div>
    </div>
  )
}

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

  // Menú con restricción RBAC: 'Equipo Administrador' solo visible para rol ADMIN
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
      visible: user?.role === "ADMIN", // Restricción estricta RBAC
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
    if (location.pathname.includes("/admin/administrators")) {
      return "Directorio de Miembros & Control de Acceso"
    }
    return "Panel Central de Control"
  }

  return (
    <div className="min-h-screen w-full flex bg-[#F8FAFC] text-[#0F172A]">
      {/* 1. SIDEBAR DESKTOP (Fiel a Vista 15A) */}
      <aside className="hidden lg:flex flex-col w-64 bg-[#0B1011] text-[#F0FDFA] border-r border-[#1B2426] shrink-0 justify-between">
        <div>
          {/* Header del Sidebar */}
          <div className="h-18 px-5 flex items-center gap-3 border-b border-[#1B2426]">
            <div className="w-10 h-10 rounded-lg bg-[#00786F] flex items-center justify-center font-black text-white text-base shadow-sm">
              SM
            </div>
            <div>
              <div className="font-extrabold text-sm tracking-wide text-white">SkillMatch Admin</div>
              <div className="text-[11px] text-[#6E8284]">Sistema de Información v2.4</div>
            </div>
          </div>

          {/* Lista de Navegación */}
          <nav className="p-3 space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-semibold transition-all ${
                      isActive
                        ? "bg-[#00786F] text-white shadow-xs"
                        : "text-[#8B9D9F] hover:text-[#F0FDFA] hover:bg-[#141C1E]"
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

        {/* Footer del Administrador en Sesión */}
        <div className="p-4 border-t border-[#1B2426] bg-[#0E1517]">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-9 h-9 rounded-full bg-[#00786F33] border border-[#00786F66] text-[#2DD4BF] flex items-center justify-center text-xs font-black shrink-0">
                {getInitials(user?.fullName)}
              </div>
              <div className="min-w-0">
                <p className="text-xs font-bold text-white truncate">{user?.fullName || "Administrador"}</p>
                <p className="text-[10px] text-[#2DD4BF] font-semibold tracking-wider uppercase">
                  Rol: {user?.role || "ADMIN"}
                </p>
              </div>
            </div>
            <button
              onClick={handleLogout}
              disabled={isLoggingOut}
              title="Cerrar Sesión"
              className="p-1.5 rounded-md text-[#8B9D9F] hover:text-white hover:bg-red-500/10 hover:border-red-500/20 transition-colors cursor-pointer"
            >
              {isLoggingOut ? (
                <Loader2 className="w-4 h-4 animate-spin text-[#2DD4BF]" />
              ) : (
                <LogOut className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>
      </aside>

      {/* 2. CONTENIDO PRINCIPAL Y TOPBAR */}
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        {/* Topbar Desktop & Mobile Header (Fiel a 15A & 17A) */}
        <header className="h-16 bg-white border-b border-[#E2E8F0] px-4 sm:px-6 flex items-center justify-between sticky top-0 z-30 shadow-xs">
          {/* Izquierda: Hamburguesa en mobile + Breadcrumb */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className="lg:hidden p-2 rounded-md text-[#0B1011] hover:bg-gray-100 cursor-pointer"
              aria-label="Abrir Menú"
            >
              {isMobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
            <div>
              <span className="text-xs text-[#64748B] hidden sm:inline">Consola de Administración / </span>
              <span className="text-xs font-bold text-[#0F172A]">{getBreadcrumbTitle()}</span>
            </div>
          </div>

          {/* Derecha: Badge de Estado del Sistema y Rol */}
          <div className="flex items-center gap-2 sm:gap-3">
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#E6F7F3] text-[#00786F] text-xs font-semibold border border-[#00786F33]">
              <Circle className="w-2 h-2 fill-[#00786F] text-[#00786F] animate-pulse" />
              <span className="hidden sm:inline">Sistema En Línea · Latencia 24ms</span>
              <span className="sm:hidden">En Línea</span>
            </div>
            <div className="hidden sm:flex items-center px-2.5 py-1 rounded bg-[#0B1011] text-[#2DD4BF] text-[10px] font-extrabold tracking-wider uppercase">
              {user?.role === "ADMIN" ? "SuperAdmin" : user?.role}
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
        <main className="flex-1 p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

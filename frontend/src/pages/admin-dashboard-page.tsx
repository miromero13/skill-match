import { useNavigate } from "react-router-dom"
import { useAuthStore } from "@/stores/auth-store"
import { Shield, LogOut, Users, BookOpen, Database, AlertCircle } from "lucide-react"

export function AdminDashboardPage() {
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()

  const handleLogout = () => {
    logout()
    navigate("/admin/login", { replace: true })
  }

  return (
    <div className="min-h-screen w-full bg-[#0F1416] text-[#F0FDFA] flex flex-col">
      {/* Header Administrativo */}
      <header className="h-16 border-b border-[#1E2629] bg-[#141C1E] px-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-md bg-[#00786F33] text-[#2DD4BF]">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <span className="text-xs font-extrabold tracking-wider text-[#2DD4BF] uppercase">
              SkillMatch Backoffice
            </span>
            <h1 className="text-sm font-bold text-[#F0FDFA]">Panel de Control de Administración</h1>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-right hidden sm:block">
            <p className="text-xs font-semibold text-[#F0FDFA]">{user?.fullName || "Administrador"}</p>
            <p className="text-[10px] text-[#8B9D9F]">{user?.email}</p>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 px-3 py-1.5 rounded-md border border-[#1E2629] bg-[#0B1011] text-[#8B9D9F] hover:text-[#F0FDFA] hover:border-red-500/50 hover:bg-red-500/10 text-xs font-semibold transition-colors cursor-pointer"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Cerrar Sesión</span>
          </button>
        </div>
      </header>

      {/* Contenido Principal */}
      <main className="flex-1 p-6 max-w-6xl mx-auto w-full flex flex-col gap-6">
        {/* Banner de Estado del Administrador */}
        <div className="p-5 rounded-xl border border-[#1E2629] bg-[#141C1E] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded bg-[#00786F33] text-[#2DD4BF] text-[10px] font-bold uppercase tracking-wider mb-2">
              Sesión Activa: Rol {user?.role}
            </div>
            <h2 className="text-lg font-bold text-[#F0FDFA]">Bienvenido al Centro de Control de SkillMatch</h2>
            <p className="text-xs text-[#8B9D9F] mt-1">
              Acceso institucional exclusivo para la gestión de catálogo de habilidades, supervisión de datasets y auditoría forense.
            </p>
          </div>
        </div>

        {/* Tarjetas de Módulos Administrativos */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-5 rounded-xl border border-[#1E2629] bg-[#141C1E] flex flex-col gap-3">
            <div className="w-9 h-9 rounded-lg bg-[#00786F33] flex items-center justify-center text-[#2DD4BF]">
              <Users className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-bold text-[#F0FDFA]">Equipo Administrador</h3>
            <p className="text-xs text-[#8B9D9F]">Gestión y creación de cuentas institucionales con rol ADMIN.</p>
          </div>

          <div className="p-5 rounded-xl border border-[#1E2629] bg-[#141C1E] flex flex-col gap-3">
            <div className="w-9 h-9 rounded-lg bg-[#00786F33] flex items-center justify-center text-[#2DD4BF]">
              <BookOpen className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-bold text-[#F0FDFA]">Catálogo de Habilidades</h3>
            <p className="text-xs text-[#8B9D9F]">Administración de taxonomía, niveles y parámetros de intercambio.</p>
          </div>

          <div className="p-5 rounded-xl border border-[#1E2629] bg-[#141C1E] flex flex-col gap-3">
            <div className="w-9 h-9 rounded-lg bg-[#00786F33] flex items-center justify-center text-[#2DD4BF]">
              <Database className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-bold text-[#F0FDFA]">Captura & Datasets IA</h3>
            <p className="text-xs text-[#8B9D9F]">Consola de etiquetado y curaduría de modelos biométricos propios.</p>
          </div>

          <div className="p-5 rounded-xl border border-[#1E2629] bg-[#141C1E] flex flex-col gap-3">
            <div className="w-9 h-9 rounded-lg bg-[#00786F33] flex items-center justify-center text-[#2DD4BF]">
              <AlertCircle className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-bold text-[#F0FDFA]">Auditoría & Quejas</h3>
            <p className="text-xs text-[#8B9D9F]">Resolución arbitral de disputas y dictamen de pruebas sospechosas.</p>
          </div>
        </div>
      </main>
    </div>
  )
}

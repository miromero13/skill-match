import { useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { useAuthStore } from "@/stores/auth-store"
import { getMe } from "@/services/auth-service"
import {
  Users,
  BookOpen,
  Database,
  ShieldAlert,
  ArrowRight,
  Activity,
  Layers,
  Sparkles,
} from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

export function AdminDashboardPage() {
  const navigate = useNavigate()
  const { user } = useAuthStore()

  useEffect(() => {
    getMe().catch((err) => {
      console.warn("Verificación de sesión en segundo plano:", err)
    })
  }, [])

  const modules = [
    {
      title: "Equipo Administrador",
      description: "Gestión, auditoría y creación de cuentas institucionales con rol ADMIN.",
      icon: Users,
      path: "/admin/administrators",
      badge: "Gobernanza",
      color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
    },
    {
      title: "Catálogo de Habilidades",
      description: "Administración de taxonomía, niveles canónicos y parámetros de evaluación.",
      icon: BookOpen,
      path: "/admin/catalog",
      badge: "Taxonomía",
      color: "text-teal-400 bg-teal-500/10 border-teal-500/20",
    },
    {
      title: "Captura & Datasets IA",
      description: "Consola de etiquetado y curaduría de muestras para modelos biométricos locales.",
      icon: Database,
      path: "/admin/capture",
      badge: "IA Propia",
      color: "text-sky-400 bg-sky-500/10 border-sky-500/20",
    },
    {
      title: "Auditoría de Fraude",
      description: "Inspección de telemetría de evaluaciones, alertas de liveness y dictámenes.",
      icon: ShieldAlert,
      path: "/admin/fraud-audit",
      badge: "Supervisión",
      color: "text-amber-400 bg-amber-500/10 border-amber-500/20",
    },
  ]

  return (
    <div className="space-y-6 max-w-6xl mx-auto w-full">
      {/* Banner de Estado del Administrador */}
      <div className="p-5 sm:p-6 rounded-xl border border-[#1E2629] bg-[#141C1E] flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-sm">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <Badge className="bg-[#00786F33] text-[#2DD4BF] border border-[#00786F40] text-[10px] uppercase font-bold tracking-wider">
              Sesión Activa: Rol {user?.role || "ADMIN"}
            </Badge>
            <span className="text-xs text-[#8B9D9F]">• {user?.email}</span>
          </div>
          <h2 className="text-xl font-bold text-[#F0FDFA]">
            Bienvenido al Centro de Control de SkillMatch
          </h2>
          <p className="text-xs text-[#8B9D9F] max-w-2xl leading-relaxed">
            Consola centralizada para la administración de usuarios del sistema, supervisión de modelos de inferencia de visión y audio en infraestructura propia, y auditoría de integridad académica.
          </p>
        </div>
      </div>

      {/* Indicadores Rápidos de la Plataforma */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="border-[#1E2629] bg-[#141C1E] text-[#F0FDFA] shadow-xs">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardDescription className="text-xs text-[#8B9D9F]">Inferencia de IA Propia</CardDescription>
              <Sparkles className="size-4 text-[#2DD4BF]" />
            </div>
            <CardTitle className="text-lg font-bold">100% Local (ONNX)</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-[11px] text-[#8B9D9F]">
              YuNet (Detección) + SFace (Reconocimiento) activos en servidor.
            </p>
          </CardContent>
        </Card>

        <Card className="border-[#1E2629] bg-[#141C1E] text-[#F0FDFA] shadow-xs">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardDescription className="text-xs text-[#8B9D9F]">Control RBAC</CardDescription>
              <Activity className="size-4 text-[#2DD4BF]" />
            </div>
            <CardTitle className="text-lg font-bold">Ofuscación 404</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-[11px] text-[#8B9D9F]">
              Rutas administrativas ocultas para miembros y anónimos.
            </p>
          </CardContent>
        </Card>

        <Card className="border-[#1E2629] bg-[#141C1E] text-[#F0FDFA] shadow-xs">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardDescription className="text-xs text-[#8B9D9F]">Estado del Catálogo</CardDescription>
              <Layers className="size-4 text-[#2DD4BF]" />
            </div>
            <CardTitle className="text-lg font-bold">Modo Limpio</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-[11px] text-[#8B9D9F]">
              Provisionamiento exclusivo del administrador inicial.
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Módulos Principales de Administración */}
      <div>
        <h3 className="text-xs font-bold uppercase tracking-wider text-[#8B9D9F] mb-3">
          Módulos de Gestión Disponibles
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {modules.map((mod) => {
            const Icon = mod.icon
            return (
              <div
                key={mod.title}
                onClick={() => navigate(mod.path)}
                className="p-5 rounded-xl border border-[#1E2629] bg-[#141C1E] flex flex-col justify-between gap-3 cursor-pointer hover:border-[#00786F] hover:bg-[#142022] transition-all group shadow-xs"
              >
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className={`w-9 h-9 rounded-lg flex items-center justify-center transition-colors ${mod.color}`}>
                      <Icon className="w-5 h-5" />
                    </div>
                    <Badge variant="outline" className="text-[10px] border-[#1E2629] text-[#8B9D9F]">
                      {mod.badge}
                    </Badge>
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-[#F0FDFA] group-hover:text-[#2DD4BF] transition-colors">
                      {mod.title}
                    </h4>
                    <p className="text-xs text-[#8B9D9F] mt-1 line-clamp-2">
                      {mod.description}
                    </p>
                  </div>
                </div>

                <div className="flex items-center justify-end text-[11px] font-semibold text-[#2DD4BF] opacity-80 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all">
                  <span>Acceder</span>
                  <ArrowRight className="w-3.5 h-3.5 ml-1" />
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

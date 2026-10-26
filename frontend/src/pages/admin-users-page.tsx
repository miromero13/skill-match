import { useEffect, useState, useMemo } from "react"
import { useAdminStore } from "@/stores/admin-store"
import { useAuthStore } from "@/stores/auth-store"
import { CreateAdminModal } from "@/components/admin/create-admin-modal"
import {
  Search,
  UserPlus,
  Shield,
  Loader2,
  CheckCircle2,
  RotateCcw,
  Ban,
  ShieldAlert,
  Info,
} from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"

export function AdminUsersPage() {
  const {
    administrators,
    totalCount,
    isLoading,
    searchTerm,
    setSearchTerm,
    setIsCreateModalOpen,
    fetchAdministrators,
    toggleStatus,
  } = useAdminStore()

  const { user: currentUser } = useAuthStore()

  // Estado para el modal de suspensión / reactivación
  const [statusDialogTarget, setStatusDialogTarget] = useState<{
    id: string
    name: string
    email: string
    newStatus: boolean
  } | null>(null)
  const [statusReason, setStatusReason] = useState("")
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false)

  // Cargar administradores al montar
  useEffect(() => {
    fetchAdministrators()
  }, [fetchAdministrators])

  // Filtrado reactivo en memoria por término de búsqueda
  const filteredAdmins = useMemo(() => {
    if (!searchTerm.trim()) return administrators
    const term = searchTerm.toLowerCase()
    return administrators.filter(
      (admin) =>
        admin.full_name.toLowerCase().includes(term) ||
        admin.email.toLowerCase().includes(term)
    )
  }, [administrators, searchTerm])

  const handleOpenStatusModal = (id: string, name: string, email: string, newStatus: boolean) => {
    setStatusDialogTarget({ id, name, email, newStatus })
    setStatusReason("")
  }

  const handleConfirmStatusChange = async () => {
    if (!statusDialogTarget) return
    setIsUpdatingStatus(true)
    try {
      await toggleStatus(
        statusDialogTarget.id,
        statusDialogTarget.newStatus,
        statusReason.trim() || undefined
      )
      setStatusDialogTarget(null)
    } finally {
      setIsUpdatingStatus(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* 1. BARRA DE ACCIÓN Y BÚSQUEDA (Fiel a 15A & 17A) */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        {/* Buscador */}
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-gray-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <Input
            placeholder="Buscar usuario por nombre o correo..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10 h-10 bg-white border-gray-200 text-sm rounded-lg focus:border-[#00786F] focus:ring-[#00786F]"
          />
        </div>

        {/* Botón de Alta */}
        <button
          onClick={() => setIsCreateModalOpen(true)}
          className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg bg-[#00786F] hover:bg-[#00665E] text-white text-xs font-bold transition-all shadow-xs cursor-pointer shrink-0"
        >
          <UserPlus className="w-4 h-4" />
          <span>+ Dar de Alta Nuevo Administrador</span>
        </button>
      </div>

      {/* 2. TABLA DESKTOP (Vista 15A) */}
      <div className="hidden lg:block bg-white rounded-xl border border-gray-200 shadow-2xl overflow-hidden">
        {isLoading ? (
          <div className="h-64 flex flex-col items-center justify-center text-gray-400 gap-2">
            <Loader2 className="w-6 h-6 animate-spin text-[#00786F]" />
            <p className="text-xs">Cargando directorio administrativo...</p>
          </div>
        ) : filteredAdmins.length === 0 ? (
          <div className="h-64 flex flex-col items-center justify-center text-gray-400 gap-2">
            <Info className="w-8 h-8 text-gray-300" />
            <p className="text-sm font-semibold text-gray-600">No se encontraron administradores</p>
            <p className="text-xs text-gray-400">Probá modificando el término de búsqueda.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-gray-100 bg-[#F8FAFC] text-[11px] font-bold text-[#64748B] uppercase tracking-wider">
                  <th className="py-3 px-6">USUARIO (NOMBRE / CORREO)</th>
                  <th className="py-3 px-6">ROL RBAC</th>
                  <th className="py-3 px-6">HABILIDADES REGISTRADAS / ÁREA</th>
                  <th className="py-3 px-6">ESTADO DE CUENTA</th>
                  <th className="py-3 px-6 text-right">ACCIONES</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 text-xs">
                {filteredAdmins.map((admin) => {
                  const isCurrent = currentUser?.id === admin.id

                  return (
                    <tr key={admin.id} className="hover:bg-gray-50/80 transition-colors">
                      {/* Usuario */}
                      <td className="py-4 px-6">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-[#00786F15] border border-[#00786F33] text-[#00786F] flex items-center justify-center font-bold text-xs shrink-0">
                            {admin.full_name.slice(0, 2).toUpperCase()}
                          </div>
                          <div>
                            <div className="font-bold text-[#0F172A] flex items-center gap-2">
                              <span>{admin.full_name}</span>
                              {isCurrent && (
                                <span className="px-1.5 py-0.2 rounded bg-gray-100 text-[10px] text-gray-500 font-medium">
                                  Tú
                                </span>
                              )}
                            </div>
                            <div className="text-[#64748B] text-[11px]">{admin.email}</div>
                          </div>
                        </div>
                      </td>

                      {/* Rol RBAC */}
                      <td className="py-4 px-6">
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-[#00786F] text-white text-[10px] font-extrabold tracking-wider uppercase">
                          <Shield className="w-3 h-3" />
                          {admin.role}
                        </span>
                      </td>

                      {/* Asignación / Habilidades */}
                      <td className="py-4 px-6">
                        <span className="text-[#64748B] text-[11px] italic">
                          SuperAdmin de Plataforma
                        </span>
                      </td>

                      {/* Estado */}
                      <td className="py-4 px-6">
                        {admin.is_active ? (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 text-[11px] font-bold border border-emerald-200">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                            {isCurrent ? "SuperAdmin Activo" : "Activo"}
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-red-50 text-red-700 text-[11px] font-bold border border-red-200">
                            <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
                            Suspendido
                          </span>
                        )}
                      </td>

                      {/* Acciones */}
                      <td className="py-4 px-6 text-right space-x-3">
                        <button
                          onClick={() => {}}
                          className="text-[#00786F] hover:text-[#00524C] font-semibold text-xs cursor-pointer"
                        >
                          Examinar
                        </button>
                        {admin.is_active ? (
                          <button
                            onClick={() =>
                              handleOpenStatusModal(admin.id, admin.full_name, admin.email, false)
                            }
                            disabled={isCurrent}
                            title={
                              isCurrent
                                ? "No podés suspender tu propia cuenta administrativa activa"
                                : "Suspender administrador"
                            }
                            className={`font-semibold text-xs transition-colors cursor-pointer ${
                              isCurrent
                                ? "text-gray-300 cursor-not-allowed"
                                : "text-red-600 hover:text-red-700 hover:underline"
                            }`}
                          >
                            Suspender
                          </button>
                        ) : (
                          <button
                            onClick={() =>
                              handleOpenStatusModal(admin.id, admin.full_name, admin.email, true)
                            }
                            className="text-emerald-600 hover:text-emerald-700 font-semibold text-xs hover:underline cursor-pointer"
                          >
                            Reactivar
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Footer de la Tabla */}
        <div className="p-4 bg-[#F8FAFC] border-t border-gray-100 flex items-center justify-between text-xs text-[#64748B]">
          <span>Mostrando {filteredAdmins.length} de {totalCount} cuentas administrativas registradas</span>
          <span className="font-semibold text-[#00786F]">Control RBAC Estricto (RF-USR-10)</span>
        </div>
      </div>

      {/* 3. VISTA MÓVIL RESPONSIVE (Vista 17A) */}
      <div className="lg:hidden space-y-3">
        <div className="flex items-center justify-between px-1">
          <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">
            Directorio ({filteredAdmins.length} Administradores)
          </span>
        </div>

        {isLoading ? (
          <div className="p-8 text-center text-gray-400">
            <Loader2 className="w-5 h-5 animate-spin mx-auto text-[#00786F] mb-2" />
            <span className="text-xs">Cargando directorio...</span>
          </div>
        ) : filteredAdmins.length === 0 ? (
          <div className="p-6 bg-white rounded-xl border border-gray-200 text-center text-gray-400 text-xs">
            No se encontraron administradores.
          </div>
        ) : (
          filteredAdmins.map((admin) => {
            const isCurrent = currentUser?.id === admin.id

            return (
              <div
                key={admin.id}
                className="p-4 bg-white rounded-xl border border-gray-200 shadow-2xs space-y-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h2 className="text-sm font-bold text-[#0F172A] flex items-center gap-1.5">
                      <span>{admin.full_name}</span>
                      <span className="text-[10px] text-[#00786F] font-black uppercase">
                        (ADMIN)
                      </span>
                    </h2>
                    <p className="text-xs text-gray-500">{admin.email}</p>
                  </div>
                  <div>
                    {admin.is_active ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 text-[10px] font-bold border border-emerald-200">
                        Admin Activo
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-red-50 text-red-700 text-[10px] font-bold border border-red-200">
                        Suspendido
                      </span>
                    )}
                  </div>
                </div>

                <div className="text-[11px] text-gray-600 bg-gray-50 p-2 rounded-md">
                  <span className="font-semibold text-gray-700">Área: </span>
                  SuperAdmin de Plataforma
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-gray-100 text-xs">
                  <span className="text-[10px] text-gray-400">
                    {isCurrent ? "Sesión actual" : "Cuenta delegada"}
                  </span>
                  <div className="flex items-center gap-3">
                    {admin.is_active ? (
                      <button
                        onClick={() =>
                          handleOpenStatusModal(admin.id, admin.full_name, admin.email, false)
                        }
                        disabled={isCurrent}
                        className={`font-bold ${
                          isCurrent
                            ? "text-gray-300"
                            : "text-red-600 hover:text-red-700 cursor-pointer"
                        }`}
                      >
                        Suspender
                      </button>
                    ) : (
                      <button
                        onClick={() =>
                          handleOpenStatusModal(admin.id, admin.full_name, admin.email, true)
                        }
                        className="text-emerald-600 font-bold hover:underline cursor-pointer"
                      >
                        Reactivar
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* 4. MODAL ALTA DE ADMINISTRADOR (Vista 15B & 17B) */}
      <CreateAdminModal />

      {/* 5. DIÁLOGO DE CONFIRMACIÓN DE SUSPENSIÓN / REACTIVACIÓN (Auditoría RF-USR-15) */}
      <Dialog
        open={!!statusDialogTarget}
        onOpenChange={(open) => !open && setStatusDialogTarget(null)}
      >
        <DialogContent className="max-w-md bg-white text-[#0F172A] p-6 rounded-2xl border border-gray-200">
          <DialogHeader className="space-y-2">
            <div className="w-10 h-10 rounded-full bg-amber-50 text-amber-600 flex items-center justify-center">
              {statusDialogTarget?.newStatus ? (
                <RotateCcw className="w-5 h-5 text-emerald-600" />
              ) : (
                <Ban className="w-5 h-5 text-red-600" />
              )}
            </div>
            <DialogTitle className="text-base font-bold text-[#0F172A]">
              {statusDialogTarget?.newStatus
                ? "¿Reactivar cuenta administrativa?"
                : "¿Suspender cuenta administrativa?"}
            </DialogTitle>
            <DialogDescription className="text-xs text-[#64748B]">
              Estás a punto de {statusDialogTarget?.newStatus ? "reactivar" : "suspender"} el acceso de{" "}
              <strong className="text-black">{statusDialogTarget?.name}</strong> (
              {statusDialogTarget?.email}).
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 py-2">
            <label className="text-xs font-bold text-[#334155] block">
              Motivo de auditoría (RF-USR-15)
            </label>
            <Input
              placeholder={
                statusDialogTarget?.newStatus
                  ? "Ej: Reactivación tras revisión de seguridad"
                  : "Ej: Suspensión preventiva por auditoría interna"
              }
              value={statusReason}
              onChange={(e) => setStatusReason(e.target.value)}
              className="text-xs h-9 bg-[#F8FAFC]"
            />
          </div>

          <div className="flex items-center justify-end gap-2 pt-3 border-t border-gray-100">
            <button
              type="button"
              onClick={() => setStatusDialogTarget(null)}
              disabled={isUpdatingStatus}
              className="px-4 py-2 rounded-lg border border-gray-200 text-xs font-semibold text-gray-600 hover:bg-gray-50"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={handleConfirmStatusChange}
              disabled={isUpdatingStatus}
              className={`px-4 py-2 rounded-lg text-xs font-bold text-white flex items-center gap-1.5 ${
                statusDialogTarget?.newStatus
                  ? "bg-emerald-600 hover:bg-emerald-700"
                  : "bg-red-600 hover:bg-red-700"
              }`}
            >
              {isUpdatingStatus ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : statusDialogTarget?.newStatus ? (
                <CheckCircle2 className="w-3.5 h-3.5" />
              ) : (
                <ShieldAlert className="w-3.5 h-3.5" />
              )}
              <span>{statusDialogTarget?.newStatus ? "Reactivar Cuenta" : "Confirmar Suspensión"}</span>
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

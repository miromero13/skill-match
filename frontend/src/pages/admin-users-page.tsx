import { useEffect, useState, useMemo } from "react"
import { useAdminStore } from "@/stores/admin-store"
import { useAuthStore } from "@/stores/auth-store"
import { CreateAdminModal } from "@/components/admin/create-admin-modal"
import {
  Search,
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
      {/* 1. BARRA DE ACCIÓN Y BÚSQUEDA (Fiel a Vista 15A & 17A) */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        {/* Buscador */}
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-[#94A3B8] absolute left-4 top-1/2 -translate-y-1/2" />
          <Input
            placeholder="Buscar usuario por nombre o correo..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-11 h-11 bg-[#F8FAFC] border-[#E2E8F0] text-xs text-[#0F172A] rounded-[8px] focus:border-[#00786F] focus:ring-[#00786F]"
          />
        </div>

        {/* Botón de Alta Fiel a 15A */}
        <button
          onClick={() => setIsCreateModalOpen(true)}
          className="h-11 px-6 rounded-[8px] bg-[#00786F] hover:bg-[#005E57] text-white text-xs font-bold transition-all shadow-xs cursor-pointer shrink-0 flex items-center justify-center"
        >
          + Dar de Alta Nuevo Administrador
        </button>
      </div>

      {/* 2. DIRECTORIO DESKTOP CON FILAS TIPO TARJETA (Fiel a Vista 15A) */}
      <div className="hidden lg:block">
        {/* Encabezado de Columnas (Fiel a 15A) */}
        <div className="grid grid-cols-12 gap-4 px-6 py-3.5 bg-[#F8FAFC] text-[10px] font-extrabold text-[#64748B] uppercase tracking-wider rounded-[8px] mb-2 border border-[#E2E8F0]">
          <div className="col-span-3">USUARIO (NOMBRE / CORREO)</div>
          <div className="col-span-2">ROL RBAC</div>
          <div className="col-span-3">HABILIDADES REGISTRADAS (0 A N)</div>
          <div className="col-span-2">ESTADO DE CUENTA</div>
          <div className="col-span-2 text-right">ACCIONES</div>
        </div>

        {isLoading ? (
          <div className="h-64 flex flex-col items-center justify-center text-gray-400 gap-2 bg-white rounded-[8px] border border-[#E2E8F0]">
            <Loader2 className="w-6 h-6 animate-spin text-[#00786F]" />
            <p className="text-xs">Cargando directorio administrativo...</p>
          </div>
        ) : filteredAdmins.length === 0 ? (
          <div className="h-64 flex flex-col items-center justify-center text-gray-400 gap-2 bg-white rounded-[8px] border border-[#E2E8F0]">
            <Info className="w-8 h-8 text-gray-300" />
            <p className="text-sm font-semibold text-gray-600">No se encontraron administradores</p>
            <p className="text-xs text-gray-400">Probá modificando el término de búsqueda.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {filteredAdmins.map((admin) => {
              const isCurrent = currentUser?.id === admin.id

              return (
                <div
                  key={admin.id}
                  className="grid grid-cols-12 gap-4 px-6 py-4 bg-white border border-[#E2E8F0] rounded-[8px] items-center shadow-2xs hover:border-[#CBD5E1] transition-colors"
                >
                  {/* Columna 1: Usuario (Nombre / Correo) */}
                  <div className="col-span-3 min-w-0">
                    <div className="font-bold text-[#0F172A] text-xs truncate flex items-center gap-1.5">
                      <span>{admin.full_name}</span>
                      {isCurrent && (
                        <span className="text-[10px] text-gray-400 font-normal">(Tú)</span>
                      )}
                    </div>
                    <div className="text-[#64748B] text-[11px] truncate">{admin.email}</div>
                  </div>

                  {/* Columna 2: Rol RBAC (Pill verde sólido con texto blanco en 15A) */}
                  <div className="col-span-2">
                    <span className="inline-block px-3 py-1 rounded-[6px] bg-[#00786F] text-white text-[10px] font-extrabold tracking-wider uppercase">
                      {admin.role}
                    </span>
                  </div>

                  {/* Columna 3: Habilidades Registradas (0 a N) (Sin habilidades registradas en 15A) */}
                  <div className="col-span-3">
                    <span className="text-[#64748B] text-[11px]">
                      Sin habilidades registradas
                    </span>
                  </div>

                  {/* Columna 4: Estado de Cuenta (Pill estilizado de 15A) */}
                  <div className="col-span-2">
                    {admin.is_active ? (
                      isCurrent ? (
                        <span className="inline-block px-3 py-1 rounded-full bg-[#DCFCE7] text-[#00786F] text-[10px] font-extrabold">
                          SuperAdmin Activo
                        </span>
                      ) : (
                        <span className="inline-block px-3 py-1 rounded-full bg-[#DCFCE7] text-[#16A34A] text-[10px] font-extrabold">
                          Activo
                        </span>
                      )
                    ) : (
                      <span className="inline-block px-3 py-1 rounded-full bg-[#FEE2E2] text-[#DC2626] text-[10px] font-extrabold">
                        Suspendido
                      </span>
                    )}
                  </div>

                  {/* Columna 5: Acciones (Examinar y Suspender/Reactivar en 15A) */}
                  <div className="col-span-2 text-right">
                    <div className="flex items-center justify-end gap-4 text-xs font-semibold">
                      <button
                        type="button"
                        onClick={() => {}}
                        className="text-[#00786F] hover:underline cursor-pointer"
                      >
                        Examinar
                      </button>
                      {admin.is_active ? (
                        <button
                          type="button"
                          onClick={() =>
                            handleOpenStatusModal(admin.id, admin.full_name, admin.email, false)
                          }
                          disabled={isCurrent}
                          title={
                            isCurrent
                              ? "No podés suspender tu propia cuenta administrativa activa"
                              : "Suspender administrador"
                          }
                          className={`cursor-pointer transition-colors ${
                            isCurrent
                              ? "text-gray-300 cursor-not-allowed"
                              : "text-[#DC2626] hover:underline"
                          }`}
                        >
                          Suspender
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() =>
                            handleOpenStatusModal(admin.id, admin.full_name, admin.email, true)
                          }
                          className="text-[#16A34A] hover:underline cursor-pointer"
                        >
                          Reactivar
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* Footer Informativo */}
        <div className="p-4 bg-[#F8FAFC] rounded-[8px] border border-[#E2E8F0] mt-3 flex items-center justify-between text-xs text-[#64748B]">
          <span>Mostrando {filteredAdmins.length} de {totalCount} cuentas administrativas registradas</span>
          <span className="font-semibold text-[#00786F]">Control RBAC Estricto (RF-USR-10 / RF-USR-15)</span>
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

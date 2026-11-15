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
    fetchAdministrator,
    updateAdmin,
    changeAdminPassword,
    toggleStatus,
    error,
    isSubmitting,
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
  const [inspectedAdmin, setInspectedAdmin] = useState<{
    id: string
    full_name: string
    email: string
  } | null>(null)
  const [isInspecting, setIsInspecting] = useState(false)
  const [editName, setEditName] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [detailLoading, setDetailLoading] = useState(false)

  // Sincronizar directorio de administradores reales del backend
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

  const handleExamine = async (id: string) => {
    setDetailLoading(true)
    setIsInspecting(true)
    const admin = await fetchAdministrator(id)
    if (admin) {
      setInspectedAdmin({ id: admin.id, full_name: admin.full_name, email: admin.email })
      setEditName(admin.full_name)
    }
    setDetailLoading(false)
  }

  const handleUpdateName = async () => {
    if (!inspectedAdmin || editName.trim().length < 2) return
    if (await updateAdmin(inspectedAdmin.id, { full_name: editName.trim() })) {
      setInspectedAdmin({ ...inspectedAdmin, full_name: editName.trim() })
    }
  }

  const handleChangePassword = async () => {
    if (!inspectedAdmin || !newPassword) return
    if (await changeAdminPassword(inspectedAdmin.id, { password: newPassword })) {
      setNewPassword("")
    }
  }

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
    <div className="flex flex-col gap-[14px]">
      {error && !isInspecting && (
        <p role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </p>
      )}
      {/* 1. ActionBar */}
      <div className="h-[48px] px-4 bg-[#141C1E] border border-[#1E2629] rounded-[8px] flex items-center justify-between shadow-2xs">
        {/* Search */}
        <div className="w-full max-w-[320px] h-[34px] px-2.5 bg-[#0F1416] border border-[#1E2629] rounded-[6px] flex items-center gap-1.5">
          <Search className="w-3.5 h-3.5 text-[#8B9D9F] shrink-0" />
          <input
            type="text"
            placeholder="Buscar usuario por nombre o correo..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-transparent text-[11px] font-[400] text-[#F0FDFA] placeholder:text-[#67787C] outline-none"
          />
        </div>

        {/* BtnNewAdmin */}
        <button
          onClick={() => setIsCreateModalOpen(true)}
          className="h-[34px] px-3.5 rounded-[6px] bg-[#00786F] hover:bg-[#00665E] text-[#F0FDFA] text-[11px] font-[700] transition-colors cursor-pointer flex items-center justify-center shrink-0 shadow-xs"
        >
          + Dar de Alta Nuevo Administrador
        </button>
      </div>

      {/* 2. TableCard Desktop */}
      <div className="hidden lg:flex flex-col gap-2 p-[16px_20px] bg-[#141C1E] border border-[#1E2629] rounded-[10px] shadow-2xs">
        {/* TableHeaderRow */}
        <div className="h-[28px] px-3 bg-[#0F1416] rounded-[4px] flex items-center text-[10px] font-[700] text-[#8B9D9F] uppercase tracking-wider">
          <div className="w-[280px] shrink-0">USUARIO (NOMBRE / CORREO)</div>
          <div className="w-[140px] shrink-0">ROL RBAC</div>
          <div className="w-[380px] flex-1">HABILIDADES REGISTRADAS (0 A N)</div>
          <div className="w-[150px] shrink-0">ESTADO DE CUENTA</div>
          <div className="w-[120px] shrink-0 text-right">ACCIONES</div>
        </div>

        {isLoading ? (
          <div className="h-48 flex flex-col items-center justify-center text-[#8B9D9F] gap-2">
            <Loader2 className="w-5 h-5 animate-spin text-[#00786F]" />
            <p className="text-[11px]">Cargando administradores...</p>
          </div>
        ) : filteredAdmins.length === 0 ? (
          <div className="h-48 flex flex-col items-center justify-center text-[#8B9D9F] gap-2">
            <Info className="w-6 h-6 text-[#8B9D9F]/60" />
            <p className="text-[12px] font-[600] text-[#F0FDFA]">No se encontraron administradores</p>
            <p className="text-[11px] text-[#8B9D9F]">Utilizá el botón superior para dar de alta uno nuevo.</p>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {filteredAdmins.map((admin) => {
              const isCurrent = currentUser?.id === admin.id

              return (
                /* UserRow */
                <div
                  key={admin.id}
                  className="h-[48px] px-3 bg-[#0F1416] border border-[#1E2629] rounded-[6px] flex items-center hover:border-[#00786F]/40 transition-colors"
                >
                  {/* Col1 (width: 280px) */}
                  <div className="w-[280px] shrink-0 flex flex-col justify-center gap-0.5 min-w-0 pr-3">
                    <div className="text-[12px] font-[700] text-[#F0FDFA] truncate flex items-center gap-1.5">
                      <span>{admin.full_name}</span>
                      {isCurrent && (
                        <span className="text-[9px] font-[500] text-[#8B9D9F] bg-[#141C1E] px-1 rounded border border-[#1E2629]">
                          Tú
                        </span>
                      )}
                    </div>
                    <div className="text-[10px] font-[500] text-[#8B9D9F] truncate">{admin.email}</div>
                  </div>

                  {/* Col2 (width: 140px - Badge ROL RBAC) */}
                  <div className="w-[140px] shrink-0 flex items-center">
                    <span className="h-[22px] px-2 bg-[#00786F] text-[#F0FDFA] text-[9px] font-[700] rounded-[4px] inline-flex items-center uppercase tracking-wider">
                      {admin.role}
                    </span>
                  </div>

                  {/* Col3 (width: 380px - Habilidades / Área) */}
                  <div className="w-[380px] flex-1 flex items-center">
                    <span className="text-[10px] font-[400] text-[#67787C]">
                      Sin habilidades registradas
                    </span>
                  </div>

                  {/* Col4 (width: 150px - Badge Estado de Cuenta) */}
                  <div className="w-[150px] shrink-0 flex items-center">
                    {admin.is_active ? (
                      isCurrent ? (
                        <span className="h-[22px] px-2 rounded-full bg-[#00786F]/20 text-[#2DD4BF] border border-[#00786F]/30 text-[9px] font-[700] inline-flex items-center">
                          SuperAdmin Activo
                        </span>
                      ) : (
                        <span className="h-[22px] px-2 rounded-full bg-[#00786F]/20 text-[#2DD4BF] border border-[#00786F]/30 text-[9px] font-[700] inline-flex items-center">
                          Activo
                        </span>
                      )
                    ) : (
                      <span className="h-[22px] px-2 rounded-full bg-red-500/15 text-red-400 border border-red-500/30 text-[9px] font-[700] inline-flex items-center">
                        Suspendido
                      </span>
                    )}
                  </div>

                  {/* Col5 (width: 120px - Acciones) */}
                  <div className="w-[120px] shrink-0 flex items-center justify-end gap-2 text-right">
                    <button
                      type="button"
                      onClick={() => void handleExamine(admin.id)}
                      className="text-[10px] font-[600] text-[#2DD4BF] hover:underline cursor-pointer"
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
                        className={`text-[10px] font-[600] transition-colors ${
                          isCurrent
                            ? "text-[#67787C]/40 cursor-not-allowed"
                            : "text-red-400 hover:underline cursor-pointer"
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
                        className="text-[10px] font-[600] text-[#2DD4BF] hover:underline cursor-pointer"
                      >
                        Reactivar
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* Footer Conteo Real */}
        <div className="pt-2 border-t border-[#1E2629] flex items-center justify-between text-[11px] text-[#8B9D9F]">
          <span>Total: {totalCount} cuentas de administradores registradas</span>
          <span className="font-[600] text-[#2DD4BF]">Control RBAC Estricto (RF-USR-10 / RF-USR-15)</span>
        </div>
      </div>

      {/* 3. VISTA MÓVIL RESPONSIVE */}
      <div className="lg:hidden flex flex-col gap-2.5">
        <div className="px-1">
          <span className="text-[10px] font-[700] text-[#67787C] uppercase tracking-wider">
            Directorio ({filteredAdmins.length} Administradores)
          </span>
        </div>

        {isLoading ? (
          <div className="p-8 text-center text-[#8B9D9F]">
            <Loader2 className="w-5 h-5 animate-spin mx-auto text-[#00786F] mb-2" />
            <span className="text-[11px]">Cargando administradores...</span>
          </div>
        ) : filteredAdmins.length === 0 ? (
          <div className="p-6 bg-[#141C1E] rounded-[8px] border border-[#1E2629] text-center text-[#8B9D9F] text-[11px]">
            No se encontraron administradores.
          </div>
        ) : (
          filteredAdmins.map((admin) => {
            const isCurrent = currentUser?.id === admin.id

            return (
              <div
                key={admin.id}
                className="p-3.5 bg-[#141C1E] rounded-[8px] border border-[#1E2629] flex flex-col gap-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h2 className="text-[12px] font-[700] text-[#F0FDFA] flex items-center gap-1.5">
                      <span>{admin.full_name}</span>
                      <span className="text-[9px] font-[700] text-[#2DD4BF] uppercase">
                        (ADMIN)
                      </span>
                    </h2>
                    <p className="text-[10px] text-[#8B9D9F]">{admin.email}</p>
                  </div>
                  <div>
                    {admin.is_active ? (
                      <span className="h-[20px] px-2 rounded-full bg-[#00786F]/20 text-[#2DD4BF] border border-[#00786F]/30 text-[9px] font-[700] inline-flex items-center">
                        {isCurrent ? "SuperAdmin" : "Activo"}
                      </span>
                    ) : (
                      <span className="h-[20px] px-2 rounded-full bg-red-500/15 text-red-400 border border-red-500/30 text-[9px] font-[700] inline-flex items-center">
                        Suspendido
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-[#1E2629] text-[10px]">
                  <span className="text-[#8B9D9F]">
                    {isCurrent ? "Sesión actual" : "Cuenta delegada"}
                  </span>
                  <div className="flex items-center gap-3">
                    <button type="button" onClick={() => void handleExamine(admin.id)} className="font-[600] text-[#2DD4BF] hover:underline cursor-pointer">
                      Examinar
                    </button>
                    {admin.is_active ? (
                      <button
                        type="button"
                        onClick={() =>
                          handleOpenStatusModal(admin.id, admin.full_name, admin.email, false)
                        }
                        disabled={isCurrent}
                        className={`font-[600] ${
                          isCurrent
                            ? "text-[#67787C]/40 cursor-not-allowed"
                            : "text-red-400 hover:underline cursor-pointer"
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
                        className="text-[#2DD4BF] font-[600] hover:underline cursor-pointer"
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

      {/* 4. MODAL ALTA DE ADMINISTRADOR (Vista 15B) */}
      <CreateAdminModal />

      <Dialog
        open={isInspecting}
        onOpenChange={(open) => {
          setIsInspecting(open)
          if (!open) {
            setInspectedAdmin(null)
            setNewPassword("")
          }
        }}
      >
        <DialogContent className="max-w-lg max-h-[90dvh] overflow-y-auto bg-[#141C1E] text-[#F0FDFA] border border-[#1E2629]">
          <DialogHeader>
            <DialogTitle className="text-[#F0FDFA]">Cuenta de administrador</DialogTitle>
            <DialogDescription className="text-[#8B9D9F]">Inspeccioná y actualizá los datos de esta cuenta administrativa.</DialogDescription>
          </DialogHeader>
          {detailLoading ? (
            <Loader2 className="mx-auto my-8 h-5 w-5 animate-spin text-[#00786F]" />
          ) : inspectedAdmin ? (
            <div className="space-y-5">
              {error && <p role="alert" className="text-sm text-red-400 bg-red-500/10 p-3 rounded border border-red-500/20">{error}</p>}
              <p className="break-all text-sm text-[#8B9D9F]">{inspectedAdmin.email}</p>
              <div className="space-y-2">
                <label htmlFor="admin-full-name" className="text-sm font-medium text-[#8B9D9F]">Nombre completo</label>
                <div className="flex flex-col gap-2 sm:flex-row">
                  <Input id="admin-full-name" value={editName} onChange={(event) => setEditName(event.target.value)} className="bg-[#0F1416] border-[#1E2629] text-[#F0FDFA]" />
                  <button type="button" disabled={isSubmitting || editName.trim().length < 2} onClick={() => void handleUpdateName()} className="h-10 shrink-0 rounded-md bg-[#00786F] hover:bg-[#00665E] px-4 text-sm font-semibold text-white disabled:opacity-50 cursor-pointer">Guardar</button>
                </div>
              </div>
              <div className="space-y-2 border-t border-[#1E2629] pt-4">
                <label htmlFor="admin-new-password" className="text-sm font-medium text-[#8B9D9F]">Cambiar contraseña</label>
                <p className="text-xs text-[#67787C]">Las sesiones existentes permanecerán activas.</p>
                <Input id="admin-new-password" type="password" autoComplete="new-password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} className="bg-[#0F1416] border-[#1E2629] text-[#F0FDFA]" />
                <button type="button" disabled={isSubmitting || newPassword.length < 8} onClick={() => void handleChangePassword()} className="h-10 w-full rounded-md border border-[#1E2629] bg-[#0F1416] hover:bg-[#1A2225] px-4 text-sm font-semibold text-[#F0FDFA] disabled:opacity-50 cursor-pointer">Actualizar contraseña</button>
              </div>
            </div>
          ) : error ? (
            <p role="alert" className="text-sm text-red-400">{error}</p>
          ) : null}
        </DialogContent>
      </Dialog>

      {/* 5. DIÁLOGO DE CONFIRMACIÓN DE SUSPENSIÓN / REACTIVACIÓN (Auditoría RF-USR-15) */}
      <Dialog
        open={!!statusDialogTarget}
        onOpenChange={(open) => !open && setStatusDialogTarget(null)}
      >
        <DialogContent className="max-w-md bg-[#141C1E] text-[#F0FDFA] p-6 rounded-[14px] border border-[#1E2629]">
          <DialogHeader className="space-y-2">
            <div className="w-10 h-10 rounded-full bg-amber-500/10 text-amber-400 flex items-center justify-center border border-amber-500/20">
              {statusDialogTarget?.newStatus ? (
                <RotateCcw className="w-5 h-5 text-[#2DD4BF]" />
              ) : (
                <Ban className="w-5 h-5 text-red-400" />
              )}
            </div>
            <DialogTitle className="text-sm font-[700] text-[#F0FDFA]">
              {statusDialogTarget?.newStatus
                ? "¿Reactivar cuenta de administrador?"
                : "¿Suspender cuenta de administrador?"}
            </DialogTitle>
            <DialogDescription className="text-[11px] text-[#8B9D9F]">
              Estás a punto de {statusDialogTarget?.newStatus ? "reactivar" : "suspender"} el acceso de{" "}
              <strong className="text-[#F0FDFA]">{statusDialogTarget?.name}</strong> (
              {statusDialogTarget?.email}).
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2 py-2">
            <label className="text-[10px] font-[700] text-[#8B9D9F] uppercase tracking-wider block">
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
              className="text-[11px] h-[36px] bg-[#0F1416] border-[#1E2629] text-[#F0FDFA] placeholder:text-[#67787C] rounded-[6px]"
            />
          </div>

          <div className="flex items-center justify-end gap-2 pt-3 border-t border-[#1E2629]">
            <button
              type="button"
              onClick={() => setStatusDialogTarget(null)}
              disabled={isUpdatingStatus}
              className="px-4 h-[36px] rounded-[6px] border border-[#1E2629] bg-[#0F1416] text-[11px] font-[600] text-[#8B9D9F] hover:text-[#F0FDFA] hover:bg-[#1A2225] cursor-pointer"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={handleConfirmStatusChange}
              disabled={isUpdatingStatus}
              className={`px-4 h-[36px] rounded-[6px] text-[11px] font-[700] text-white flex items-center gap-1.5 cursor-pointer ${
                statusDialogTarget?.newStatus
                  ? "bg-[#00786F] hover:bg-[#00665E]"
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

import { useState, useId } from "react"
import { useAdminStore } from "@/stores/admin-store"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Eye, EyeOff, Loader2, Check, ShieldCheck, Lock } from "lucide-react"

export function CreateAdminModal() {
  const {
    isCreateModalOpen,
    setIsCreateModalOpen,
    createAdmin,
    isSubmitting,
    error: storeError,
    clearError,
    administrators,
  } = useAdminStore()

  const [fullName, setFullName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  const nameInputId = useId()
  const emailInputId = useId()
  const passwordInputId = useId()

  // Validación de unicidad de correo en tiempo real gestionada con Zustand (HU-10)
  const cleanEmail = email.trim().toLowerCase()
  const isEmailDuplicate = cleanEmail.length > 0 && administrators.some(
    (a) => a.email.toLowerCase() === cleanEmail
  )

  // Validación en tiempo real de robustez de contraseña
  const hasMinLength = password.length >= 8
  const hasUppercase = /[A-Z]/.test(password)
  const hasLowercase = /[a-z]/.test(password)
  const hasNumber = /\d/.test(password)
  const hasSpecialChar = /[!@#$%^&*(),.?":{}|<>\-_=+\\/[\]]/.test(password)
  const isPasswordValid = hasMinLength && hasUppercase && hasLowercase && hasNumber && hasSpecialChar

  const isFormValid =
    fullName.trim().length >= 2 &&
    /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleanEmail) &&
    !isEmailDuplicate &&
    isPasswordValid

  const resetForm = () => {
    setFullName("")
    setEmail("")
    setPassword("")
    setShowPassword(false)
    setLocalError(null)
    clearError()
  }

  const handleClose = () => {
    if (isSubmitting) return
    resetForm()
    setIsCreateModalOpen(false)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!isFormValid || isSubmitting) return

    setLocalError(null)
    const success = await createAdmin({
      full_name: fullName.trim(),
      email: cleanEmail,
      password,
    })

    if (success) {
      resetForm()
    }
  }

  const activeError = localError || storeError

  return (
    <Dialog open={isCreateModalOpen} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl bg-white text-[#0F172A] p-6 sm:p-8 rounded-2xl border border-gray-200 shadow-2xl">
        <DialogHeader className="space-y-1.5 pb-4 border-b border-gray-100">
          <div className="flex items-center gap-2 text-[#00786F]">
            <ShieldCheck className="w-5 h-5" />
            <span className="text-xs font-bold uppercase tracking-wider">Control de Acceso RBAC</span>
          </div>
          <DialogTitle className="text-lg sm:text-xl font-black text-[#0B1011] tracking-tight">
            <span className="hidden sm:inline">DAR DE ALTA NUEVO USUARIO / ADMINISTRADOR (RBAC)</span>
            <span className="sm:hidden">ALTA DE ADMINISTRADOR</span>
          </DialogTitle>
          <DialogDescription className="text-xs text-[#64748B]">
            Asigná credenciales institucionales, rol jerárquico y permisos de auditoría forense o resolución de disputas.
          </DialogDescription>
        </DialogHeader>

        {activeError && (
          <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs font-medium">
            {activeError}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5 pt-2">
          {/* Fila 1: Nombre y Correo Institucional */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor={nameInputId} className="text-xs font-bold text-[#334155] uppercase tracking-wider">
                Nombre y Apellido
              </Label>
              <Input
                id={nameInputId}
                placeholder="Ing. Gonzalo Martínez"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
                className="h-10 bg-[#F8FAFC] border-gray-200 text-sm focus:border-[#00786F] focus:ring-[#00786F]"
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label htmlFor={emailInputId} className="text-xs font-bold text-[#334155] uppercase tracking-wider">
                  Correo Institucional
                </Label>
                {isEmailDuplicate && (
                  <span className="text-[10px] font-bold text-red-500">
                    Correo ya registrado
                  </span>
                )}
              </div>
              <Input
                id={emailInputId}
                type="email"
                placeholder="gonzalo.martinez@admin.skillmatch.io"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value)
                  if (storeError) clearError()
                }}
                required
                className={`h-10 bg-[#F8FAFC] text-sm focus:ring-[#00786F] ${
                  isEmailDuplicate
                    ? "border-red-400 focus:border-red-500"
                    : "border-gray-200 focus:border-[#00786F]"
                }`}
              />
            </div>
          </div>

          {/* Fila 2: Contraseña Inicial y Verificaciones */}
          <div className="space-y-2">
            <Label htmlFor={passwordInputId} className="text-xs font-bold text-[#334155] uppercase tracking-wider">
              Contraseña Inicial
            </Label>
            <div className="relative">
              <Input
                id={passwordInputId}
                type={showPassword ? "text" : "password"}
                placeholder="Contraseña inicial robusta"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="h-10 pr-10 bg-[#F8FAFC] border-gray-200 text-sm focus:border-[#00786F] focus:ring-[#00786F]"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 cursor-pointer"
                aria-label={showPassword ? "Ocultar contraseña" : "Ver contraseña"}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>

            {/* Checklist de Robustez de Contraseña */}
            <div className="p-3 bg-[#F8FAFC] rounded-lg border border-gray-100 text-[11px] grid grid-cols-2 sm:grid-cols-3 gap-2 text-gray-500">
              <span className={`flex items-center gap-1 ${hasMinLength ? "text-emerald-600 font-semibold" : ""}`}>
                <Check className={`w-3.5 h-3.5 ${hasMinLength ? "opacity-100" : "opacity-30"}`} />
                Mínimo 8 caracteres
              </span>
              <span className={`flex items-center gap-1 ${hasUppercase ? "text-emerald-600 font-semibold" : ""}`}>
                <Check className={`w-3.5 h-3.5 ${hasUppercase ? "opacity-100" : "opacity-30"}`} />
                Una mayúscula
              </span>
              <span className={`flex items-center gap-1 ${hasLowercase ? "text-emerald-600 font-semibold" : ""}`}>
                <Check className={`w-3.5 h-3.5 ${hasLowercase ? "opacity-100" : "opacity-30"}`} />
                Una minúscula
              </span>
              <span className={`flex items-center gap-1 ${hasNumber ? "text-emerald-600 font-semibold" : ""}`}>
                <Check className={`w-3.5 h-3.5 ${hasNumber ? "opacity-100" : "opacity-30"}`} />
                Un número
              </span>
              <span className={`flex items-center gap-1 col-span-2 sm:col-span-1 ${hasSpecialChar ? "text-emerald-600 font-semibold" : ""}`}>
                <Check className={`w-3.5 h-3.5 ${hasSpecialChar ? "opacity-100" : "opacity-30"}`} />
                Carácter especial (!@#$...)
              </span>
            </div>
          </div>

          {/* Fila 3: Rol en la Plataforma y Estado (Fiel a 15B) */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <span className="text-xs font-bold text-[#334155] uppercase tracking-wider block">
                Rol en la Plataforma
              </span>
              <div className="h-10 px-3 bg-[#F8FAFC] border border-gray-200 rounded-md flex items-center justify-between text-xs font-semibold text-[#0B1011]">
                <span>Auditor Forense & Mediador Arbitral</span>
                <span className="px-1.5 py-0.5 rounded bg-[#00786F] text-white text-[10px] font-black">
                  ADMIN
                </span>
              </div>
            </div>

            <div className="space-y-1.5">
              <span className="text-xs font-bold text-[#334155] uppercase tracking-wider block">
                Estado de Cuenta
              </span>
              <div className="h-10 px-3 bg-[#F8FAFC] border border-gray-200 rounded-md flex items-center justify-between text-xs font-semibold text-emerald-700">
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  Activa (Verificada)
                </span>
                <Lock className="w-3.5 h-3.5 text-gray-400" />
              </div>
            </div>
          </div>

          {/* Privilegios Concedidos */}
          <div className="text-[11px] text-gray-500 flex items-center gap-1.5 pt-1">
            <ShieldCheck className="w-3.5 h-3.5 text-[#00786F]" />
            <span>Privilegios RBAC asignados: Telemetría WebRTC, Retención Escrow, Moderación Forense.</span>
          </div>

          {/* Botones de Acción (Fiel a 15B & 17B) */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-100">
            <button
              type="button"
              onClick={handleClose}
              disabled={isSubmitting}
              className="px-5 py-2.5 rounded-lg border border-gray-200 text-xs font-bold text-gray-700 hover:bg-gray-50 transition-colors cursor-pointer disabled:opacity-50"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={!isFormValid || isSubmitting}
              className="px-6 py-2.5 rounded-lg bg-[#00786F] hover:bg-[#00665E] text-white text-xs font-bold transition-all shadow-sm flex items-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Creando Administrador...</span>
                </>
              ) : (
                <>
                  <span className="hidden sm:inline">Crear Administrador y Enviar Acceso ✓</span>
                  <span className="sm:hidden">Crear y Enviar Credenciales ✓</span>
                </>
              )}
            </button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

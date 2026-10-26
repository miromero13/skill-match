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
import { Eye, EyeOff, Loader2, Check, ShieldCheck } from "lucide-react"

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
      <DialogContent className="max-w-2xl bg-white text-[#0F172A] p-7 sm:p-8 rounded-[16px] border border-[#E2E8F0] shadow-2xl">
        <DialogHeader className="space-y-1 pb-2">
          <DialogTitle className="text-base sm:text-lg font-black text-[#0B1011] tracking-tight uppercase">
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

        <form onSubmit={handleSubmit} className="space-y-4 pt-1">
          {/* Fila 1: Nombre y Correo Institucional (Fiel a 15B) */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor={nameInputId} className="text-[10px] font-extrabold text-[#475569] uppercase tracking-wider block">
                NOMBRE Y APELLIDO:
              </Label>
              <Input
                id={nameInputId}
                placeholder="Ing. Gonzalo Martínez"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
                className="h-11 bg-[#F8FAFC] border-[#E2E8F0] rounded-[6px] text-xs font-medium text-[#0F172A] focus:border-[#00786F] focus:ring-[#00786F]"
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label htmlFor={emailInputId} className="text-[10px] font-extrabold text-[#475569] uppercase tracking-wider block">
                  CORREO INSTITUCIONAL:
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
                className={`h-11 bg-[#F8FAFC] rounded-[6px] text-xs font-medium text-[#0F172A] focus:ring-[#00786F] ${
                  isEmailDuplicate
                    ? "border-red-400 focus:border-red-500"
                    : "border-[#E2E8F0] focus:border-[#00786F]"
                }`}
              />
            </div>
          </div>

          {/* Fila 2: Rol en la Plataforma y Estado (Fiel a 15B) */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <span className="text-[10px] font-extrabold text-[#475569] uppercase tracking-wider block">
                ROL EN LA PLATAFORMA:
              </span>
              <div className="h-11 px-3 bg-[#F8FAFC] border border-[#E2E8F0] rounded-[6px] flex items-center justify-between text-xs font-bold text-[#0F172A]">
                <span>Auditor Forense & Mediador Arbitral</span>
                <span className="text-[#64748B] text-xs">▾</span>
              </div>
            </div>

            <div className="space-y-1.5">
              <span className="text-[10px] font-extrabold text-[#475569] uppercase tracking-wider block">
                ESTADO DE CUENTA:
              </span>
              <div className="h-11 px-3 bg-[#F8FAFC] border border-[#E2E8F0] rounded-[6px] flex items-center justify-between text-xs font-bold text-[#0F172A]">
                <span>Activa (Verificada)</span>
                <span className="text-[#64748B] text-xs">▾</span>
              </div>
            </div>
          </div>

          {/* Fila 3: Contraseña Inicial y Verificaciones (RF-USR-10 / HU-10) */}
          <div className="space-y-2 pt-1">
            <Label htmlFor={passwordInputId} className="text-[10px] font-extrabold text-[#475569] uppercase tracking-wider block">
              CONTRASEÑA INICIAL:
            </Label>
            <div className="relative">
              <Input
                id={passwordInputId}
                type={showPassword ? "text" : "password"}
                placeholder="Contraseña inicial robusta"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="h-11 pr-10 bg-[#F8FAFC] border-[#E2E8F0] rounded-[6px] text-xs font-medium text-[#0F172A] focus:border-[#00786F] focus:ring-[#00786F]"
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
            <div className="p-3 bg-[#F8FAFC] rounded-[6px] border border-[#E2E8F0] text-[11px] grid grid-cols-2 sm:grid-cols-3 gap-2 text-gray-500">
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

          {/* Privilegios Concedidos en Mobile (Fiel a 17B) */}
          <div className="sm:hidden text-[11px] text-[#64748B] flex items-center gap-1.5 pt-1">
            <ShieldCheck className="w-3.5 h-3.5 text-[#00786F]" />
            <span>Privilegios: Telemetría WebRTC, Retención Escrow ✓</span>
          </div>

          {/* Botones de Acción (Fiel a Vista 15B) */}
          <div className="flex items-center gap-3 pt-3">
            <button
              type="button"
              onClick={handleClose}
              disabled={isSubmitting}
              className="h-12 px-8 rounded-[6px] bg-[#F1F5F9] hover:bg-[#E2E8F0] text-[#334155] text-xs font-bold transition-colors cursor-pointer disabled:opacity-50 shrink-0"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={!isFormValid || isSubmitting}
              className="h-12 flex-1 rounded-[6px] bg-[#00786F] hover:bg-[#005E57] text-white text-xs font-bold transition-all shadow-sm flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
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

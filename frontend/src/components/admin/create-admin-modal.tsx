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
import { Eye, EyeOff, Loader2, Check } from "lucide-react"

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
      {/* Dialog_Alta_Administrador: width: 680px, padding: 24px 28px, gap: 14px, cornerRadius: 14px, fill: #FFFFFF, stroke: #E3E7E8 (Fiel a OpenPencil n8555) */}
      <DialogContent className="max-w-[680px] w-full bg-white text-[#090B0C] p-0 rounded-[14px] border border-[#E3E7E8] shadow-2xl overflow-hidden">
        <div className="p-[24px_28px] flex flex-col gap-[14px]">
          {/* Head (OpenPencil n8556) */}
          <DialogHeader className="space-y-[4px] text-left">
            <DialogTitle className="text-[15px] font-[800] text-[#090B0C] tracking-tight uppercase leading-snug">
              DAR DE ALTA NUEVO USUARIO / ADMINISTRADOR (RBAC)
            </DialogTitle>
            <DialogDescription className="text-[11px] font-[400] text-[#67787C] leading-normal">
              Asigná credenciales institucionales, rol jerárquico y permisos de auditoría forense o resolución de disputas.
            </DialogDescription>
          </DialogHeader>

          {activeError && (
            <div className="p-2.5 rounded-[6px] bg-red-50 border border-red-200 text-red-700 text-[11px] font-medium">
              {activeError}
            </div>
          )}

          <form onSubmit={handleSubmit} className="flex flex-col gap-[14px]">
            {/* RowInputs1: layout: horizontal, gap: 12px (OpenPencil n8559) */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-[12px]">
              {/* Field: Nombre y Apellido (n8560) */}
              <div className="flex flex-col gap-[3px]">
                <Label htmlFor={nameInputId} className="text-[10px] font-[700] text-[#67787C] uppercase tracking-wider block">
                  NOMBRE Y APELLIDO:
                </Label>
                <Input
                  id={nameInputId}
                  placeholder="Ing. Gonzalo Martínez"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required
                  className="h-[36px] bg-[#F8FAFB] border-[#E3E7E8] rounded-[6px] px-[10px] text-[11px] font-[500] text-[#090B0C] placeholder:text-[#67787C]/60 focus:border-[#00786F] focus:ring-[#00786F]"
                />
              </div>

              {/* Field: Correo Institucional (n8564) */}
              <div className="flex flex-col gap-[3px]">
                <div className="flex items-center justify-between">
                  <Label htmlFor={emailInputId} className="text-[10px] font-[700] text-[#67787C] uppercase tracking-wider block">
                    CORREO INSTITUCIONAL:
                  </Label>
                  {isEmailDuplicate && (
                    <span className="text-[9px] font-[700] text-red-500">
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
                  className={`h-[36px] bg-[#F8FAFB] rounded-[6px] px-[10px] text-[11px] font-[500] text-[#090B0C] placeholder:text-[#67787C]/60 focus:ring-[#00786F] ${
                    isEmailDuplicate
                      ? "border-red-400 focus:border-red-500"
                      : "border-[#E3E7E8] focus:border-[#00786F]"
                  }`}
                />
              </div>
            </div>

            {/* RowInputs2: layout: horizontal, gap: 12px (OpenPencil n8568) */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-[12px]">
              {/* Field: Rol en la Plataforma (n8569) */}
              <div className="flex flex-col gap-[3px]">
                <span className="text-[10px] font-[700] text-[#67787C] uppercase tracking-wider block">
                  ROL EN LA PLATAFORMA:
                </span>
                <div className="h-[36px] px-[10px] bg-[#F8FAFB] border border-[#E3E7E8] rounded-[6px] flex items-center justify-between text-[11px] font-[500] text-[#090B0C] cursor-default select-none">
                  <span>Auditor Forense & Mediador Arbitral ▾</span>
                </div>
              </div>

              {/* Field: Estado de Cuenta (n8573) */}
              <div className="flex flex-col gap-[3px]">
                <span className="text-[10px] font-[700] text-[#67787C] uppercase tracking-wider block">
                  ESTADO DE CUENTA:
                </span>
                <div className="h-[36px] px-[10px] bg-[#F8FAFB] border border-[#E3E7E8] rounded-[6px] flex items-center justify-between text-[11px] font-[500] text-[#090B0C] cursor-default select-none">
                  <span>Activa (Verificada) ▾</span>
                </div>
              </div>
            </div>

            {/* Fila Contraseña Inicial (Requisito Funcional RF-USR-10 / HU-10) */}
            <div className="flex flex-col gap-[3px]">
              <Label htmlFor={passwordInputId} className="text-[10px] font-[700] text-[#67787C] uppercase tracking-wider block">
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
                  className="h-[36px] pr-9 bg-[#F8FAFB] border-[#E3E7E8] rounded-[6px] px-[10px] text-[11px] font-[500] text-[#090B0C] placeholder:text-[#67787C]/60 focus:border-[#00786F] focus:ring-[#00786F]"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#67787C] hover:text-[#090B0C] cursor-pointer"
                  aria-label={showPassword ? "Ocultar contraseña" : "Ver contraseña"}
                >
                  {showPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                </button>
              </div>

              {/* Checklist de Robustez de Contraseña */}
              <div className="p-2 bg-[#F8FAFB] rounded-[6px] border border-[#E3E7E8] text-[10px] grid grid-cols-2 sm:grid-cols-3 gap-1.5 text-[#67787C] mt-1">
                <span className={`flex items-center gap-1 ${hasMinLength ? "text-emerald-600 font-semibold" : ""}`}>
                  <Check className={`w-3 h-3 ${hasMinLength ? "opacity-100" : "opacity-30"}`} />
                  Mínimo 8 caracteres
                </span>
                <span className={`flex items-center gap-1 ${hasUppercase ? "text-emerald-600 font-semibold" : ""}`}>
                  <Check className={`w-3 h-3 ${hasUppercase ? "opacity-100" : "opacity-30"}`} />
                  Una mayúscula
                </span>
                <span className={`flex items-center gap-1 ${hasLowercase ? "text-emerald-600 font-semibold" : ""}`}>
                  <Check className={`w-3 h-3 ${hasLowercase ? "opacity-100" : "opacity-30"}`} />
                  Una minúscula
                </span>
                <span className={`flex items-center gap-1 ${hasNumber ? "text-emerald-600 font-semibold" : ""}`}>
                  <Check className={`w-3 h-3 ${hasNumber ? "opacity-100" : "opacity-30"}`} />
                  Un número
                </span>
                <span className={`flex items-center gap-1 col-span-2 sm:col-span-1 ${hasSpecialChar ? "text-emerald-600 font-semibold" : ""}`}>
                  <Check className={`w-3 h-3 ${hasSpecialChar ? "opacity-100" : "opacity-30"}`} />
                  Especial (!@#$...)
                </span>
              </div>
            </div>

            {/* Actions: layout: horizontal, gap: 10px (OpenPencil n8582) */}
            <div className="flex items-center gap-[10px] pt-[6px]">
              {/* BtnCancel: width: 140px, height: 42px, cornerRadius: 8px, fill: #F4F4F5 (n8583) */}
              <button
                type="button"
                onClick={handleClose}
                disabled={isSubmitting}
                className="w-[140px] h-[42px] rounded-[8px] bg-[#F4F4F5] hover:bg-[#E4E4E7] text-[#67787C] text-[11px] font-[700] transition-colors cursor-pointer disabled:opacity-50 flex items-center justify-center shrink-0"
              >
                Cancelar
              </button>

              {/* BtnSubmit: width: fill_container, height: 42px, cornerRadius: 8px, fill: #00786F (n8585) */}
              <button
                type="submit"
                disabled={!isFormValid || isSubmitting}
                className="flex-1 h-[42px] rounded-[8px] bg-[#00786F] hover:bg-[#00665E] text-[#F0FDFA] text-[11px] font-[700] transition-all shadow-xs flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Creando Administrador...</span>
                  </>
                ) : (
                  <span>Crear Administrador y Enviar Acceso ✓</span>
                )}
              </button>
            </div>
          </form>
        </div>
      </DialogContent>
    </Dialog>
  )
}

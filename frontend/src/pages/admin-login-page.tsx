import React, { useState } from "react"
import { useNavigate } from "react-router-dom"
import { ShieldAlert, Lock, Mail, Eye, EyeOff, ArrowRight, Loader2 } from "lucide-react"
import { loginAdmin } from "@/services/admin-auth-service"
import { ApiError } from "@/types/api"

export function AdminLoginPage() {
  const navigate = useNavigate()

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [rememberMe, setRememberMe] = useState(true)
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMessage(null)

    if (!email.trim() || !password) {
      setErrorMessage("Por favor ingrese su correo institucional y contraseña.")
      return
    }

    try {
      setIsLoading(true)
      await loginAdmin({
        email: email.trim(),
        password,
        remember_me: rememberMe,
      })

      // Redirección al panel de administración tras éxito
      navigate("/admin/dashboard", { replace: true })
    } catch (error) {
      if (error instanceof ApiError) {
        setErrorMessage(error.message)
      } else {
        setErrorMessage("Error de conexión al autenticar con el servidor de seguridad.")
      }
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div
      className="min-h-screen w-full flex items-center justify-center p-4 sm:p-6"
      style={{ backgroundColor: "#0F1416" }}
    >
      <div
        className="w-full max-w-[480px] rounded-[14px] p-6 sm:p-9 flex flex-col gap-5 border transition-all"
        style={{
          backgroundColor: "#141C1E",
          borderColor: "#1E2629",
          boxShadow: "0 20px 40px -15px rgba(0,0,0,0.7)",
        }}
      >
        {/* Badge Superior */}
        <div className="flex items-center gap-2">
          <div
            className="px-2.5 py-1 rounded-[4px] flex items-center gap-1.5"
            style={{ backgroundColor: "rgba(0, 120, 111, 0.2)" }}
          >
            <Lock className="w-3 h-3 text-[#2DD4BF]" />
            <span className="text-[10px] font-extrabold tracking-wider text-[#2DD4BF] uppercase">
              SISTEMA DE INFORMACIÓN & AUDITORÍA
            </span>
          </div>
        </div>

        {/* Título y Subtítulo */}
        <div className="flex flex-col gap-1.5">
          <h1 className="text-lg sm:text-xl font-extrabold text-[#F0FDFA] tracking-tight">
            ACCESO ADMINISTRATIVO SEGURO
          </h1>
          <p className="text-xs text-[#8B9D9F] leading-relaxed">
            Portal restringido para la gestión de catálogo, auditoría forense y control arbitral.
          </p>
        </div>

        {/* Mensaje de Error en Alerta */}
        {errorMessage && (
          <div
            role="alert"
            className="flex items-start gap-2.5 p-3 rounded-md border text-xs"
            style={{
              backgroundColor: "rgba(239, 68, 68, 0.1)",
              borderColor: "rgba(239, 68, 68, 0.3)",
              color: "#FCA5A5",
            }}
          >
            <ShieldAlert className="w-4 h-4 shrink-0 text-red-400 mt-0.5" />
            <span className="leading-snug">{errorMessage}</span>
          </div>
        )}

        {/* Formulario */}
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {/* Campo Correo Institucional */}
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="admin-email"
              className="text-[10px] font-bold text-[#8B9D9F] uppercase tracking-wider"
            >
              CORREO ELECTRÓNICO INSTITUCIONAL:
            </label>
            <div
              className="relative flex items-center rounded-md border transition-colors focus-within:border-[#2DD4BF]"
              style={{ backgroundColor: "#0B1011", borderColor: "#1E2629" }}
            >
              <Mail className="absolute left-3 w-4 h-4 text-[#8B9D9F]" />
              <input
                id="admin-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin.gonzalo@skillmatch.io"
                autoComplete="email"
                required
                disabled={isLoading}
                className="w-full h-11 pl-9 pr-3 text-xs font-medium text-[#F0FDFA] bg-transparent outline-none placeholder:text-[#526466]"
              />
            </div>
          </div>

          {/* Campo Contraseña */}
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="admin-password"
              className="text-[10px] font-bold text-[#8B9D9F] uppercase tracking-wider"
            >
              CONTRASEÑA CIFRADA:
            </label>
            <div
              className="relative flex items-center rounded-md border transition-colors focus-within:border-[#2DD4BF]"
              style={{ backgroundColor: "#0B1011", borderColor: "#1E2629" }}
            >
              <Lock className="absolute left-3 w-4 h-4 text-[#8B9D9F]" />
              <input
                id="admin-password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••••••••••"
                autoComplete="current-password"
                required
                disabled={isLoading}
                className="w-full h-11 pl-9 pr-10 text-xs font-medium text-[#F0FDFA] bg-transparent outline-none placeholder:text-[#526466]"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 text-[#8B9D9F] hover:text-[#F0FDFA] transition-colors focus:outline-none"
                tabIndex={-1}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Switch / Checkbox Recordar Sesión */}
          <div className="flex items-center gap-2 pt-1">
            <input
              id="remember-me"
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              className="w-3.5 h-3.5 rounded accent-[#00786F] cursor-pointer"
            />
            <label
              htmlFor="remember-me"
              className="text-[11px] font-medium text-[#8B9D9F] cursor-pointer select-none"
            >
              Recordar sesión en esta terminal de trabajo
            </label>
          </div>

          {/* Botón de Submit */}
          <button
            type="submit"
            disabled={isLoading}
            className="w-full h-11 mt-2 rounded-lg font-bold text-xs text-[#F0FDFA] flex items-center justify-center gap-2 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed hover:brightness-110 active:scale-[0.99]"
            style={{ backgroundColor: "#00786F" }}
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-[#F0FDFA]" />
                <span>Verificando credenciales...</span>
              </>
            ) : (
              <>
                <span>Ingresar al Panel de Control</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>

        {/* Cuadro de Notificación de Seguridad (RF-USR-16 y Política 404) */}
        <div
          className="p-3 rounded-md flex items-start gap-2"
          style={{ backgroundColor: "#0B1011", border: "1px solid #1A2326" }}
        >
          <p className="text-[10px] text-[#8B9D9F] leading-relaxed">
            <span className="font-semibold text-[#A2B4B6]">Política de Seguridad:</span> Intentos no
            autorizados son bloqueados tras 5 fallos consecutivos. Solicitudes de miembros comunes
            responden con <span className="font-mono text-[#F0FDFA]">404 Not Found</span>.
          </p>
        </div>
      </div>
    </div>
  )
}

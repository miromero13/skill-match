import React, { useState } from "react"
import { useNavigate } from "react-router-dom"
import { ShieldAlert, Loader2 } from "lucide-react"
import { loginAdmin } from "@/services/admin-auth-service"
import { ApiError } from "@/types/api"

export function AdminLoginPage() {
  const navigate = useNavigate()

  const [email, setEmail] = useState("admin.gonzalo@skillmatch.io")
  const [password, setPassword] = useState("SuperSecretAdminPassword123!")
  const [rememberMe, setRememberMe] = useState(true)
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
      className="min-h-screen w-full flex items-center justify-center p-4 selection:bg-[#00786F] selection:text-white"
      style={{ backgroundColor: "#0F1416" }}
    >
      {/* Caja de Login exacta del prototipo (480px, padding 36px 32px, gap 16px, radius 14px) */}
      <div
        className="w-full max-w-[480px] rounded-[14px] flex flex-col gap-4 border"
        style={{
          backgroundColor: "#141C1E",
          borderColor: "#1E2629",
          padding: "36px 32px",
          boxShadow: "0 24px 48px -12px rgba(0,0,0,0.8)",
        }}
      >
        {/* Badge: SISTEMA DE INFORMACIÓN & AUDITORÍA */}
        <div className="flex items-center">
          <div
            className="px-2 py-1 rounded-[4px] inline-flex items-center"
            style={{ backgroundColor: "#00786F33" }}
          >
            <span
              className="text-[9px] font-extrabold tracking-wider uppercase leading-none"
              style={{ color: "#2DD4BF" }}
            >
              SISTEMA DE INFORMACIÓN & AUDITORÍA
            </span>
          </div>
        </div>

        {/* Encabezado: Título y Subtítulo */}
        <div className="flex flex-col gap-1">
          <h1
            className="text-[16px] font-extrabold tracking-tight leading-snug"
            style={{ color: "#F0FDFA" }}
          >
            ACCESO ADMINISTRATIVO SEGURO
          </h1>
          <p
            className="text-[11px] font-normal leading-normal"
            style={{ color: "#8B9D9F" }}
          >
            Portal restringido para la gestión de catálogo, auditoría forense y control arbitral.
          </p>
        </div>

        {/* Mensaje de Error (si ocurre alguno) */}
        {errorMessage && (
          <div
            role="alert"
            className="flex items-start gap-2.5 p-3 rounded-[6px] border text-[11px]"
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
          <div className="flex flex-col gap-1">
            <label
              htmlFor="admin-email"
              className="text-[10px] font-bold uppercase tracking-wider"
              style={{ color: "#8B9D9F" }}
            >
              CORREO ELECTRÓNICO INSTITUCIONAL:
            </label>
            <div
              className="w-full h-[40px] rounded-[6px] border flex items-center px-3 transition-colors focus-within:border-[#2DD4BF]"
              style={{
                backgroundColor: "#0B1011",
                borderColor: "#1E2629",
              }}
            >
              <input
                id="admin-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin.gonzalo@skillmatch.io"
                autoComplete="email"
                required
                disabled={isLoading}
                className="w-full text-[11px] font-medium bg-transparent outline-none placeholder:text-[#425052]"
                style={{ color: "#F0FDFA" }}
              />
            </div>
          </div>

          {/* Campo Contraseña */}
          <div className="flex flex-col gap-1">
            <label
              htmlFor="admin-password"
              className="text-[10px] font-bold uppercase tracking-wider"
              style={{ color: "#8B9D9F" }}
            >
              CONTRASEÑA CIFRADA:
            </label>
            <div
              className="w-full h-[40px] rounded-[6px] border flex items-center px-3 transition-colors focus-within:border-[#2DD4BF]"
              style={{
                backgroundColor: "#0B1011",
                borderColor: "#1E2629",
              }}
            >
              <input
                id="admin-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••••••••••"
                autoComplete="current-password"
                required
                disabled={isLoading}
                className="w-full text-[11px] font-medium tracking-widest bg-transparent outline-none placeholder:text-[#425052]"
                style={{ color: "#F0FDFA" }}
              />
            </div>
          </div>

          {/* Fila Checkbox: Recordar sesión */}
          <div className="flex items-center gap-2 pt-0.5">
            <input
              id="remember-me"
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              className="w-3.5 h-3.5 rounded accent-[#00786F] cursor-pointer"
            />
            <label
              htmlFor="remember-me"
              className="text-[10px] font-medium cursor-pointer select-none"
              style={{ color: "#8B9D9F" }}
            >
              Recordar sesión en esta terminal de trabajo
            </label>
          </div>

          {/* Botón Principal: Ingresar al Panel de Control ➔ */}
          <button
            type="submit"
            disabled={isLoading}
            className="w-full h-[44px] rounded-[8px] font-bold text-[12px] flex items-center justify-center gap-2 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed hover:brightness-110 active:scale-[0.99]"
            style={{
              backgroundColor: "#00786F",
              color: "#F0FDFA",
            }}
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Verificando credenciales...</span>
              </>
            ) : (
              <span>Ingresar al Panel de Control ➔</span>
            )}
          </button>
        </form>

        {/* Caja de Aviso de Seguridad y Ofuscación 404 */}
        <div
          className="rounded-[6px] p-2.5 flex items-center"
          style={{
            backgroundColor: "#0B1011",
          }}
        >
          <p
            className="text-[9px] font-medium leading-[14px]"
            style={{ color: "#8B9D9F" }}
          >
            Política de Seguridad: Intentos no autorizados son bloqueados tras 5 fallos. Solicitudes de
            miembros comunes responden con 404 Not Found.
          </p>
        </div>
      </div>
    </div>
  )
}

import * as React from "react"
import { useNavigate, useLocation, Link } from "react-router-dom"
import { Loader2 } from "lucide-react"
import { useAuthStore } from "@/stores/auth-store"
import { loginWithGoogle } from "@/services/auth-service"
import { toast } from "sonner"

/**
 * Vista 28 (Web Desktop) & Vista 30 (Mobile): Registro & Autenticación de Miembros (Social & OTP)
 * Especificación OpenPencil:
 * - Contenedor: AuthCard_Member (520px desktop / full mobile, fill #FFFFFF, stroke #E3E7E8, radius 16px desktop / 14px mobile, gap 16px)
 * - Fondo: #F8FAFB
 * - Logo: "SkillMatch" (24px font 900 #00786F)
 * - Título: "CREAR CUENTA O INICIAR SESIÓN" (16px font 800 #090B0C) / Mobile: "ACCESO RÁPIDO SIN CONTRASEÑAS"
 * - Subtítulo: "Accedé al ecosistema de intercambio sin contraseñas mediante tus cuentas verificadas." (11px font 400 #67787C)
 * - Botones Sociales: Google y GitHub (42px, fill #FFFFFF, stroke #E3E7E8, radius 8px, text 11px font 700 #090B0C)
 * - Divisor: "o con WhatsApp" (10px font 600 #67787C, stroke #E3E7E8)
 * - Teléfono OTP: prefijo "🇺🇾 +598 ▾" + input (38px, fill #F8FAFB, stroke #E3E7E8, radius 8px)
 * - Slots OTP: 6 dígitos (36x42px, fill #E6F4F2, stroke 1.5px #00786F, radius 6px, text 16px font 800 #00786F)
 * - Botón Submit: "Verificar Código y Entrar a SkillMatch ➔" (44px, fill #00786F, radius 8px, text 12px font 700 #F0FDFA)
 * - Términos: "Al registrarte aceptás las Normas de Integridad y el uso de Escrow en trueques." (9px font 400 #67787C)
 */
export function MemberLoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { isAuthenticated, user } = useAuthStore()

  const [isLoading, setIsLoading] = React.useState(false)
  const [phoneNumber, setPhoneNumber] = React.useState("")
  const [otp, setOtp] = React.useState<string[]>(["", "", "", "", "", ""])

  const otpInputRefs = React.useRef<(HTMLInputElement | null)[]>([])
  const googleBtnContainerRef = React.useRef<HTMLDivElement>(null)

  const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID
  const isGoogleConfigured = Boolean(
    googleClientId &&
      !googleClientId.includes("tu-google-client-id") &&
      googleClientId.includes(".apps.googleusercontent.com")
  )

  // Redirigir si ya está autenticado con rol MEMBER
  React.useEffect(() => {
    if (isAuthenticated && user?.role === "MEMBER") {
      const from = (location.state as { from?: { pathname: string } })?.from?.pathname || "/app"
      navigate(from, { replace: true })
    }
  }, [isAuthenticated, user, navigate, location])

  // Inicializar Google Identity Services button si el SDK está disponible
  React.useEffect(() => {
    if (!isGoogleConfigured) return

    let attempts = 0
    const interval = setInterval(() => {
      attempts++
      const win = window as unknown as {
        google?: {
          accounts?: {
            id?: {
              initialize: (config: {
                client_id: string
                callback: (res: { credential: string }) => void
              }) => void
              renderButton: (
                parent: HTMLElement,
                options: {
                  theme?: "outline" | "filled_blue" | "filled_black"
                  size?: "large" | "medium" | "small"
                  width?: number | string
                  text?: "signin_with" | "signup_with" | "continue_with"
                  shape?: "rectangular" | "pill" | "circle" | "square"
                  locale?: string
                }
              ) => void
            }
          }
        }
      }

      if (win.google?.accounts?.id && googleBtnContainerRef.current) {
        clearInterval(interval)
        try {
          win.google.accounts.id.initialize({
            client_id: googleClientId!,
            callback: async (response: { credential: string }) => {
              setIsLoading(true)
              try {
                await loginWithGoogle(response.credential)
                toast.success("¡Inicio de sesión exitoso!", {
                  description: "Bienvenido a SkillMatch.",
                })
                const from = (location.state as { from?: { pathname: string } })?.from?.pathname || "/app"
                navigate(from, { replace: true })
              } catch (err: unknown) {
                const message = err instanceof Error ? err.message : "Error al autenticar con Google"
                toast.error("Error de autenticación", { description: message })
              } finally {
                setIsLoading(false)
              }
            },
          })

          googleBtnContainerRef.current.innerHTML = ""
          win.google.accounts.id.renderButton(googleBtnContainerRef.current, {
            theme: "outline",
            size: "large",
            width: "360",
            text: "continue_with",
            shape: "rectangular",
            locale: "es",
          })
        } catch (e) {
          console.warn("No se pudo inicializar Google Identity Services renderButton:", e)
        }
      }

      if (attempts > 20) {
        clearInterval(interval)
      }
    }, 300)

    return () => clearInterval(interval)
  }, [isGoogleConfigured, googleClientId, navigate, location])

  // Autenticación directa con Google (GIS o Mock Dev)
  const handleGoogleSignIn = async () => {
    setIsLoading(true)

    try {
      const win = window as unknown as {
        google?: {
          accounts?: {
            id?: {
              prompt: (notification?: (status: { isNotDisplayed: () => boolean; isSkippedMoment: () => boolean }) => void) => void
            }
          }
        }
      }

      if (win.google?.accounts?.id && isGoogleConfigured) {
        win.google.accounts.id.prompt()
        setIsLoading(false)
        return
      }

      // MODO DESARROLLO / PRUEBAS LOCALES (Token simulado con JWT UTF-8 seguro)
      const headerStr = JSON.stringify({ alg: "HS256", typ: "JWT" })
      const header = btoa(unescape(encodeURIComponent(headerStr)))
      const now = Math.floor(Date.now() / 1000)
      const payloadStr = JSON.stringify({
        iss: "https://accounts.google.com",
        sub: "google-member-dev-12345",
        email: "carlos.mendez@skillmatch.io",
        name: "Carlos Mendez",
        picture: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=256&h=256&q=80",
        email_verified: true,
        iat: now,
        exp: now + 3600,
      })
      const payload = btoa(unescape(encodeURIComponent(payloadStr)))
      const mockIdToken = `${header}.${payload}.devsignature`

      await loginWithGoogle(mockIdToken)

      toast.success("¡Inicio de sesión completado!", {
        description: "Sesión iniciada como Carlos Méndez (Modo Desarrollo).",
      })

      const from = (location.state as { from?: { pathname: string } })?.from?.pathname || "/app"
      navigate(from, { replace: true })
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Error de comunicación con el servidor"
      toast.error("Error al autenticar", { description: message })
    } finally {
      setIsLoading(false)
    }
  }

  // Notificar disponibilidad próxima de GitHub
  const handleGitHubSignIn = () => {
    toast.info("Autenticación con GitHub", {
      description: "Próximamente disponible en esta versión.",
    })
  }

  // Manejo de OTP slots (navegación entre casillas, pegado y borrado)
  const handleOtpChange = (index: number, value: string) => {
    const digit = value.replace(/\D/g, "").slice(-1)
    const newOtp = [...otp]
    newOtp[index] = digit
    setOtp(newOtp)

    if (digit && index < 5) {
      otpInputRefs.current[index + 1]?.focus()
    }
  }

  const handleOtpKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace" && !otp[index] && index > 0) {
      otpInputRefs.current[index - 1]?.focus()
    }
  }

  const handleOtpPaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault()
    const pastedData = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6)
    if (!pastedData) return

    const newOtp = [...otp]
    for (let i = 0; i < pastedData.length; i++) {
      newOtp[i] = pastedData[i]
    }
    setOtp(newOtp)
    const nextIndex = Math.min(pastedData.length, 5)
    otpInputRefs.current[nextIndex]?.focus()
  }

  // Verificación de OTP
  const handleVerifyOtp = () => {
    const enteredCode = otp.join("")
    if (enteredCode.length < 6 && !phoneNumber) {
      toast.info("WhatsApp OTP", {
        description: "Ingresá tu número de teléfono para recibir el código de acceso.",
      })
      return
    }
    toast.info("WhatsApp OTP", {
      description: "Canal OTP en fase de homologación. Por favor accedé mediante Google.",
    })
  }

  return (
    <div className="flex min-h-[calc(100vh-64px)] w-full items-center justify-center p-4 sm:p-6 bg-[#F8FAFB]">
      {/* Contenedor AuthCard_Member (OpenPencil n8912 / n9173) */}
      <div className="w-full max-w-[520px] bg-white border border-[#E3E7E8] rounded-[14px] sm:rounded-[16px] p-6 sm:p-[32px_36px] flex flex-col items-center gap-4 shadow-2xs">
        
        {/* Logo (OpenPencil n8913: 24px font 900 #00786F) */}
        <Link
          to="/"
          className="text-[22px] sm:text-[24px] font-[900] text-[#00786F] tracking-tight hover:opacity-95 transition-opacity"
        >
          SkillMatch
        </Link>

        {/* Título (OpenPencil n8914: 16px font 800 #090B0C / n9175) */}
        <h1 className="text-[14px] sm:text-[16px] font-[800] text-[#090B0C] tracking-wide text-center uppercase">
          <span className="hidden sm:inline">CREAR CUENTA O INICIAR SESIÓN</span>
          <span className="sm:hidden">ACCESO RÁPIDO SIN CONTRASEÑAS</span>
        </h1>

        {/* Subtítulo (OpenPencil n8915: 11px font 400 #67787C) */}
        <p className="text-[11px] font-[400] text-[#67787C] text-center leading-normal max-w-[420px]">
          Accedé al ecosistema de intercambio sin contraseñas mediante tus cuentas verificadas.
        </p>

        {/* SocialBtns (OpenPencil n8916: gap 8px) */}
        <div className="w-full flex flex-col gap-2">
          {/* Btn_Google (OpenPencil n8917: 42px, radius 8px, stroke #E3E7E8, text 11px font 700) */}
          <button
            type="button"
            disabled={isLoading}
            onClick={handleGoogleSignIn}
            className="h-[42px] w-full rounded-[8px] bg-white hover:bg-[#F8FAFB] border border-[#E3E7E8] text-[#090B0C] font-[700] text-[11px] flex items-center justify-center gap-[10px] transition-colors cursor-pointer shadow-2xs disabled:opacity-50"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-[#00786F]" />
                <span>Conectando con Google...</span>
              </>
            ) : (
              <>
                <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24">
                  <path
                    fill="#4285F4"
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  />
                  <path
                    fill="#34A853"
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                  />
                  <path
                    fill="#EA4335"
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                  />
                </svg>
                <span>Continuar con Google</span>
              </>
            )}
          </button>

          {/* Btn_GitHub (OpenPencil n8920: 42px, radius 8px, stroke #E3E7E8, text 11px font 700) */}
          <button
            type="button"
            disabled={isLoading}
            onClick={handleGitHubSignIn}
            className="h-[42px] w-full rounded-[8px] bg-white hover:bg-[#F8FAFB] border border-[#E3E7E8] text-[#090B0C] font-[700] text-[11px] flex items-center justify-center gap-[10px] transition-colors cursor-pointer shadow-2xs disabled:opacity-50"
          >
            <svg className="w-4 h-4 shrink-0 text-[#090B0C]" viewBox="0 0 24 24" fill="currentColor">
              <path
                fillRule="evenodd"
                clipRule="evenodd"
                d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
              />
            </svg>
            <span>Continuar con GitHub</span>
          </button>
        </div>

        {/* GIS contenedor oculto para render nativo si está disponible */}
        <div ref={googleBtnContainerRef} className="hidden" />

        {/* Divider (OpenPencil n8923: stroke #E3E7E8, text 10px font 600 #67787C) */}
        <div className="w-full flex items-center gap-[10px] my-0.5">
          <div className="flex-1 h-[1px] bg-[#E3E7E8]" />
          <span className="text-[10px] font-[600] text-[#67787C] uppercase tracking-wider select-none">
            o con WhatsApp
          </span>
          <div className="flex-1 h-[1px] bg-[#E3E7E8]" />
        </div>

        {/* PhoneBox (OpenPencil n8927: gap 6px) */}
        <div className="w-full flex flex-col gap-[6px]">
          <label
            htmlFor="member-phone-input"
            className="text-[10px] font-[700] text-[#67787C] uppercase tracking-wider"
          >
            NÚMERO DE TELÉFONO PARA CÓDIGO OTP:
          </label>
          <div className="h-[38px] w-full bg-[#F8FAFB] border border-[#E3E7E8] rounded-[8px] px-[10px] flex items-center gap-[8px] focus-within:border-[#00786F] transition-colors">
            <span className="text-[11px] font-[700] text-[#090B0C] shrink-0 select-none">
              🇺🇾 +598 ▾
            </span>
            <input
              id="member-phone-input"
              type="tel"
              value={phoneNumber}
              onChange={(e) => setPhoneNumber(e.target.value)}
              placeholder="099 482 910"
              disabled={isLoading}
              className="w-full bg-transparent text-[11px] font-[600] text-[#090B0C] placeholder:text-[#67787C] outline-none"
            />
          </div>
        </div>

        {/* OtpContainer (OpenPencil n8932: gap 6px, slots 36x42 fill #E6F4F2 stroke 1.5px #00786F) */}
        <div className="w-full flex flex-col items-center gap-[6px] my-0.5">
          <span className="text-[10px] font-[600] text-[#00786F]">
            Código de 6 dígitos enviado por WhatsApp:
          </span>
          <div className="flex items-center justify-center gap-[8px]">
            {otp.map((digit, idx) => (
              <input
                key={idx}
                ref={(el) => {
                  otpInputRefs.current[idx] = el
                }}
                type="text"
                inputMode="numeric"
                maxLength={1}
                value={digit}
                onChange={(e) => handleOtpChange(idx, e.target.value)}
                onKeyDown={(e) => handleOtpKeyDown(idx, e)}
                onPaste={handleOtpPaste}
                placeholder="•"
                disabled={isLoading}
                className="w-[36px] h-[42px] bg-[#E6F4F2] border-[1.5px] border-[#00786F] rounded-[6px] text-center text-[16px] font-[800] text-[#00786F] placeholder:text-[#00786F]/40 outline-none focus:ring-1 focus:ring-[#00786F] transition-all"
              />
            ))}
          </div>
        </div>

        {/* BtnSubmitOtp (OpenPencil n8947: 44px, fill #00786F, radius 8px, text 12px font 700 #F0FDFA) */}
        <button
          type="button"
          disabled={isLoading}
          onClick={handleVerifyOtp}
          className="h-[44px] w-full rounded-[8px] bg-[#00786F] hover:bg-[#00665E] text-[#F0FDFA] text-[12px] font-[700] flex items-center justify-center transition-colors cursor-pointer shadow-2xs disabled:opacity-50"
        >
          Verificar Código y Entrar a SkillMatch ➔
        </button>

        {/* Terms (OpenPencil n8949: 9px font 400 #67787C) */}
        <p className="text-[9px] font-[400] text-[#67787C] text-center leading-normal">
          Al registrarte aceptás las Normas de Integridad y el uso de Escrow en trueques.
        </p>

      </div>
    </div>
  )
}

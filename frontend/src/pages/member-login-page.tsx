import * as React from "react"
import { useNavigate, useLocation, Link } from "react-router-dom"
import { Capacitor } from "@capacitor/core"
import { Button } from "@/components/ui/button"
import { getNativeGoogleCredential, nativeGoogleConfigured } from "@/services/native-google-service"
import { Loader2, ShieldCheck, Clock } from "lucide-react"
import { useAuthStore } from "@/stores/auth-store"
import { loginWithGoogle } from "@/services/auth-service"
import { Card, CardContent } from "@/components/ui/card"
import { toast } from "sonner"

interface GoogleIdentity {
  initialize: (config: { client_id: string; callback: (response: { credential: string }) => void }) => void
  renderButton: (parent: HTMLElement, options: Record<string, string | number>) => void
}

/** Web uses GIS; native platforms use Google SDK. Both verify identity on the backend. */
export function MemberLoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { isAuthenticated, user } = useAuthStore()
  const [isLoading, setIsLoading] = React.useState(false)
  const [sdkUnavailable, setSdkUnavailable] = React.useState(false)
  const busy = React.useRef(false)
  const mounted = React.useRef(true)
  React.useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  const native = Capacitor.isNativePlatform()
  const container = React.useRef<HTMLDivElement>(null)
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined
  const configured = Boolean(clientId?.endsWith(".apps.googleusercontent.com") && !clientId.includes("tu-google-client-id")) && (!native || nativeGoogleConfigured())
  const from = (location.state as { from?: { pathname: string } } | null)?.from?.pathname || "/app"

  React.useEffect(() => {
    if (isAuthenticated && user?.role === "MEMBER") navigate(from, { replace: true })
  }, [isAuthenticated, user, navigate, from])

  React.useEffect(() => {
    if (native || !configured || !clientId) return
    let attempts = 0
    let disposed = false
    const timer = window.setInterval(() => {
      const google = (window as unknown as { google?: { accounts?: { id?: GoogleIdentity } } }).google
      const identity = google?.accounts?.id
      if (identity && container.current) {
        window.clearInterval(timer)
        try {
          identity.initialize({
            client_id: clientId,
            callback: async ({ credential }) => {
              if (disposed || busy.current) return
              busy.current = true
              setIsLoading(true)
              try {
                await loginWithGoogle(credential)
                if (!disposed) navigate(from, { replace: true })
              } catch (error: unknown) {
                if (!disposed) toast.error(error instanceof Error ? error.message : "Error al autenticar con Google")
              } finally {
                busy.current = false
                if (!disposed) setIsLoading(false)
              }
            },
          })
          container.current.replaceChildren()
          identity.renderButton(container.current, {
            theme: "outline",
            size: "large",
            width: Math.min(400, container.current.clientWidth || 360),
            text: "continue_with",
            shape: "rectangular",
            locale: "es",
          })
        } catch {
          setSdkUnavailable(true)
        }
      } else if (++attempts >= 20) {
        window.clearInterval(timer)
        setSdkUnavailable(true)
      }
    }, 300)
    return () => { disposed = true; window.clearInterval(timer) }
  }, [native, configured, clientId, navigate, from])

  const authenticateNative = async () => {
    if (busy.current || !configured) return
    busy.current = true
    setIsLoading(true)
    try {
      const credential = await getNativeGoogleCredential()
      if (!mounted.current) return
      await loginWithGoogle(credential)
      if (mounted.current) navigate(from, { replace: true })
    } catch (error: unknown) {
      if (mounted.current) toast.error(error instanceof Error ? error.message : "Error al autenticar con Google")
    } finally {
      busy.current = false
      if (mounted.current) setIsLoading(false)
    }
  }

  return (
    <div className="relative min-h-[calc(100vh-64px)] w-full flex items-center justify-center p-4 sm:p-6 bg-[#0B0F10] overflow-hidden selection:bg-[#00786F] selection:text-white">
      {/* Ambient background decoration */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-[#00786F]/10 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute bottom-10 right-10 w-[300px] h-[300px] bg-[#2DD4BF]/5 rounded-full blur-[120px] pointer-events-none" />

      <Card className="relative w-full max-w-[420px] bg-[#141C1E] border-[#1E2629] shadow-2xl rounded-2xl overflow-hidden backdrop-blur-sm">
        {/* Subtle top emerald accent */}
        <div className="h-1 w-full bg-gradient-to-r from-transparent via-[#00786F] to-transparent" />

        <CardContent className="flex flex-col items-center gap-6 p-6 sm:p-8 text-center">
          {/* Brand header */}
          <div className="flex flex-col items-center gap-2.5">
            <Link
              to="/"
              className="inline-flex items-center gap-1.5 text-2xl font-black tracking-tight text-[#F0FDFA] hover:opacity-90 transition-opacity"
            >
              <span>Skill</span>
              <span className="text-[#2DD4BF]">Match</span>
            </Link>

            <div className="space-y-1">
              <h1 className="text-base sm:text-lg font-bold tracking-tight text-[#F0FDFA]">
                Crear cuenta o iniciar sesión
              </h1>
              <p className="text-xs text-[#8B9D9F] max-w-xs mx-auto leading-relaxed">
                Accedé sin contraseñas con tu cuenta verificada de Google a la comunidad de intercambio.
              </p>
            </div>
          </div>

          {/* Action area */}
          <div className="w-full space-y-3">
            {!configured ? (
              <div
                role="alert"
                className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-400 text-center font-medium"
              >
                El acceso con Google no está configurado.
              </div>
            ) : native ? (
              <Button
                variant="outline"
                className="w-full h-11 border-[#1E2629] bg-[#0F1416] text-[#F0FDFA] hover:bg-[#1A2225] hover:border-[#00786F]/50 font-semibold cursor-pointer shadow-xs flex items-center justify-center gap-2.5 transition-all text-xs sm:text-sm"
                disabled={isLoading}
                onClick={() => void authenticateNative()}
              >
                <svg className="h-4 w-4 shrink-0" viewBox="0 0 24 24">
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
              </Button>
            ) : sdkUnavailable ? (
              <div
                role="alert"
                className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-400 text-center font-medium"
              >
                No se pudo cargar Google. Revisá la conexión y recargá la página.
              </div>
            ) : (
              <div
                ref={container}
                className={`w-full min-w-0 min-h-[44px] flex justify-center items-center [&>div]:!w-full [&_iframe]:!w-full [&_iframe]:!min-w-full ${
                  isLoading ? "pointer-events-none opacity-50" : ""
                }`}
                aria-disabled={isLoading}
              />
            )}

            {isLoading && (
              <p
                role="status"
                className="flex items-center justify-center gap-2 text-xs text-[#2DD4BF] font-medium pt-1"
              >
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span>Conectando con Google...</span>
              </p>
            )}
          </div>

          {/* Guarantees list */}
          <div className="w-full pt-4 border-t border-[#1E2629] space-y-2.5 text-left">
            <div className="flex items-start gap-2.5 text-xs text-[#8B9D9F]">
              <ShieldCheck className="h-4 w-4 text-[#2DD4BF] shrink-0 mt-0.5" />
              <span>
                <strong className="text-[#F0FDFA]">Identidad verificada:</strong> Acceso con Google OAuth 2.0, sin contraseñas locales.
              </span>
            </div>
            <div className="flex items-start gap-2.5 text-xs text-[#8B9D9F]">
              <Clock className="h-4 w-4 text-[#2DD4BF] shrink-0 mt-0.5" />
              <span>
                <strong className="text-[#F0FDFA]">Billetera de tiempo:</strong> Tu billetera se crea con saldo inicial de 0 SkillPoints, sin recargas ni retiros.
              </span>
            </div>
          </div>

          {/* Footer note */}
          <p className="text-[11px] text-[#67787C] text-center leading-relaxed">
            Al continuar, aceptas las normas de la comunidad y la verificación de identidad de SkillMatch.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}

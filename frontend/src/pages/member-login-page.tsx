import * as React from "react"
import { useNavigate, useLocation, Link } from "react-router-dom"
import { Capacitor } from "@capacitor/core"
import { Button } from "@/components/ui/button"
import { getNativeGoogleCredential, nativeGoogleConfigured } from "@/services/native-google-service"
import { Loader2 } from "lucide-react"
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
    <div className="flex min-h-[calc(100vh-64px)] items-center justify-center bg-background p-4 sm:p-6">
      <Card className="w-full max-w-[400px] shadow-sm">
        <CardContent className="flex flex-col items-center gap-5 p-6 text-center sm:p-8">
          <Link to="/" className="text-2xl font-black tracking-tight text-primary">SkillMatch</Link>
          <div className="space-y-1">
            <h1 className="text-base font-extrabold uppercase">Crear cuenta o iniciar sesión</h1>
            <p className="text-sm text-muted-foreground">
              Accedé sin contraseñas con tu cuenta verificada de Google.
            </p>
          </div>
          {!configured ? (
            <p role="alert" className="text-sm text-destructive">El acceso con Google no está configurado.</p>
          ) : native ? (
            <Button variant="outline" className="w-full h-10" disabled={isLoading} onClick={() => void authenticateNative()}>Continuar con Google</Button>
          ) : sdkUnavailable ? (
            <p role="alert" className="text-sm text-destructive">No se pudo cargar Google. Revisá la conexión y recargá la página.</p>
          ) : (
            <div
              ref={container}
              className={`w-full flex justify-center [&>div]:!w-full [&_iframe]:!w-full [&_iframe]:!min-w-full ${
                isLoading ? "pointer-events-none opacity-50" : ""
              }`}
              aria-disabled={isLoading}
            />
          )}
          {isLoading && <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" />Conectando con Google...</p>}
          <p className="text-xs text-muted-foreground">Tu billetera se crea con saldo inicial de 0 SkillPoints, sin recargas ni retiros.</p>
        </CardContent>
      </Card>
    </div>
  )
}

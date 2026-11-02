import * as React from "react"
import { useNavigate, useLocation, Link } from "react-router-dom"
import { ShieldCheck, Sparkles } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { useAuthStore } from "@/stores/auth-store"
import { loginWithGoogle } from "@/services/auth-service"
import { toast } from "sonner"

export function MemberLoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { isAuthenticated, user } = useAuthStore()
  const [isLoading, setIsLoading] = React.useState(false)

  const googleBtnContainerRef = React.useRef<HTMLDivElement>(null)

  const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID
  const isGoogleConfigured = Boolean(
    googleClientId &&
      !googleClientId.includes("tu-google-client-id") &&
      googleClientId.includes(".apps.googleusercontent.com")
  )
  const [isGisButtonRendered, setIsGisButtonRendered] = React.useState(false)

  // Redirigir si ya está autenticado
  React.useEffect(() => {
    if (isAuthenticated && user?.role === "MEMBER") {
      const from = (location.state as { from?: { pathname: string } })?.from?.pathname || "/app"
      navigate(from, { replace: true })
    }
  }, [isAuthenticated, user, navigate, location])

  // Inicializar Google Identity Services button si el SDK y el client_id están listos
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
                  description: "Bienvenido a tu panel de SkillMatch.",
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
          setIsGisButtonRendered(true)
        } catch (e) {
          console.warn("No se pudo inicializar Google Identity Services renderButton:", e)
        }
      }

      // Detener tras 20 intentos (~6 segundos)
      if (attempts > 20) {
        clearInterval(interval)
      }
    }, 300)

    return () => clearInterval(interval)
  }, [isGoogleConfigured, googleClientId, navigate, location])


  /**
   * Manejador del botón cuando se pulsa directamente (o fallback para desarrollo)
   */
  const handleGoogleSignIn = async () => {
    setIsLoading(true)

    try {
      const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID
      const win = window as unknown as {
        google?: {
          accounts?: {
            id?: {
              prompt: (notification?: (status: { isNotDisplayed: () => boolean; isSkippedMoment: () => boolean }) => void) => void
            }
          }
        }
      }

      // Si Google GIS está disponible y configurado
      if (win.google?.accounts?.id && googleClientId && !googleClientId.includes("tu-google-client-id")) {
        win.google.accounts.id.prompt()
        setIsLoading(false)
        return
      }

      // MODO DESARROLLO / PRUEBAS LOCALES (Token simulado con codificación segura UTF-8)
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


  return (
    <div className="flex min-h-[calc(100vh-64px)] w-full items-center justify-center p-4 sm:p-6 lg:p-8 bg-[#F8FAFB] dark:bg-background">
      <div className="w-full max-w-md space-y-6">
        {/* Cabecera / Identidad de Marca */}
        <div className="flex flex-col items-center text-center space-y-2">
          <Link to="/" className="flex items-center gap-2 group">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground font-black text-xl shadow-md transition-transform group-hover:scale-105">
              SM
            </div>
          </Link>
          <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-foreground">
            Acceso a la Comunidad
          </h1>
          <p className="text-xs sm:text-sm text-muted-foreground max-w-xs">
            Trueque formativo sin intermediarios. Tu nivel técnico validado con IA propia.
          </p>
        </div>

        {/* Auth Card Principal (Fiel a Vista 28 Web / Vista 30 Mobile) */}
        <Card className="border border-border/70 shadow-lg bg-card rounded-2xl overflow-hidden">
          <CardHeader className="space-y-1 pb-4 pt-6 text-center">
            <div className="mx-auto inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-[11px] font-bold text-primary mb-1">
              <Sparkles className="h-3.5 w-3.5" />
              <span>3 Certificaciones de IA Gratuitas</span>
            </div>
            <CardTitle className="text-lg font-bold">Iniciá sesión o registrate</CardTitle>
            <CardDescription className="text-xs">
              Sin contraseñas. Accedé al instante con tu cuenta de Google.
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-5 pb-6">
            {/* Si Google GIS se renderizó, mostramos el botón oficial de Google */}
            <div
              ref={googleBtnContainerRef}
              className={`w-full min-h-[44px] flex items-center justify-center ${
                !isGisButtonRendered ? "hidden" : ""
              }`}
            />

            {/* Si no se ha renderizado el botón nativo de Google GIS, mostramos el botón directo */}
            {!isGisButtonRendered && (
              <Button
                type="button"
                variant="outline"
                size="lg"
                disabled={isLoading}
                onClick={handleGoogleSignIn}
                className="w-full h-12 relative flex items-center justify-center gap-3 border-border hover:bg-muted/60 font-semibold text-xs sm:text-sm rounded-xl transition-all shadow-xs"
              >
                {/* Google SVG Logo Oficial */}
                <svg className="h-5 w-5 shrink-0" viewBox="0 0 24 24">
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
                <span>{isLoading ? "Conectando con Google..." : "Continuar con Google"}</span>
              </Button>
            )}



            {/* Ventajas / Propuesta de Valor del Miembro */}
            <div className="rounded-xl bg-muted/40 p-4 border border-border/50 space-y-2.5">
              <div className="flex items-center gap-2 text-xs font-semibold text-foreground">
                <ShieldCheck className="h-4 w-4 text-primary shrink-0" />
                <span>¿Por qué no usamos contraseñas tradicionales?</span>
              </div>
              <ul className="space-y-1.5 text-[11px] text-muted-foreground leading-relaxed pl-6 list-disc">
                <li>Mayor seguridad: protegemos tu cuenta contra robo de claves.</li>
                <li>Acceso inmediato y sin confirmaciones lentas por correo.</li>
                <li>Tus datos personales y reputación quedan vinculados a tu identidad.</li>
              </ul>
            </div>

            {/* Microcopy de Términos */}
            <p className="text-[10px] text-center text-muted-foreground leading-normal">
              Al continuar, aceptás los{" "}
              <Link to="/" className="underline hover:text-primary">
                Términos de Convivencia
              </Link>{" "}
              y el{" "}
              <Link to="/" className="underline hover:text-primary">
                Código de Honor de SkillMatch
              </Link>
              .
            </p>
          </CardContent>
        </Card>

        {/* Footer info de regreso */}
        <div className="text-center">
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
          >
            <span>← Volver al sitio institucional</span>
          </Link>
        </div>
      </div>
    </div>
  )
}

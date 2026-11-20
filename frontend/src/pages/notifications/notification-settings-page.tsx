import { useEffect, useRef, useState } from "react"
import { Link, useBlocker } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { useNotificationStore } from "@/stores/notification-store"
import { useAuthStore, getAuthSessionVersion } from "@/stores/auth-store"
import {
  getWebPushCapability,
  requestWebPushSubscription,
  revokeWebPushSubscription,
  type WebPushCapability,
} from "@/services/web-push-service"
import { toast } from "sonner"

export function NotificationSettingsPage() {
  const state = useNotificationStore()
  const title = useRef<HTMLHeadingElement>(null)
  const version = useAuthStore(() => getAuthSessionVersion())
  const [pushCapability, setPushCapability] = useState<WebPushCapability | null>(
    null
  )
  const [pushBusy, setPushBusy] = useState(false)
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      useAuthStore.getState().isAuthenticated &&
      state.dirty &&
      currentLocation.pathname !== nextLocation.pathname
  )
  useEffect(() => {
    title.current?.focus()
    void useNotificationStore.getState().loadPreferences()
    const refresh = () => {
      void useNotificationStore.getState().loadPreferences()
    }
    window.addEventListener("focus", refresh)
    return () => window.removeEventListener("focus", refresh)
  }, [version])
  useEffect(() => {
    let active = true
    void getWebPushCapability().then((capability) => {
      if (active) setPushCapability(capability)
    })
    return () => {
      active = false
    }
  }, [version])
  useEffect(() => {
    if (!state.dirty) return
    const prevent = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ""
    }
    window.addEventListener("beforeunload", prevent)
    return () => window.removeEventListener("beforeunload", prevent)
  }, [state.dirty])
  const draft = state.draft
  const disabled = state.preferencesSaving || state.preferencesLoading
  return (
    <section className="mx-auto w-full max-w-3xl min-w-0 space-y-5 p-4 sm:p-6">
      <Button asChild variant="outline">
        <Link to="/notifications">Volver a la bandeja</Link>
      </Button>
      <h1 ref={title} tabIndex={-1} className="text-xl font-bold">
        Preferencias de notificaciones
      </h1>
      <p className="text-sm text-muted-foreground">
        Estas preferencias se aplican a los avisos futuros. Tu historial se
        conserva. Push y correo guardan tu elección; su entrega estará
        disponible con la integración correspondiente.
      </p>
      {state.preferencesLoading && <p role="status">Cargando preferencias…</p>}
      {state.preferencesError && <p role="alert">{state.preferencesError}</p>}
      {state.preferencesConflict && (
        <p role="alert">
          Hay una configuración más reciente. Recárgala antes de guardar; se
          descartará tu borrador.
        </p>
      )}
      {!draft && !state.preferencesLoading && (
        <Button onClick={() => void state.loadPreferences()}>Reintentar</Button>
      )}
      {draft && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Canales</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {(
                [
                  ["in_app", "En la aplicación"],
                  ["push", "Push"],
                  ["email", "Correo electrónico"],
                ] as const
              ).map(([key, label]) => (
                <div
                  key={key}
                  className="flex min-h-11 items-center justify-between gap-4"
                >
                  <Label htmlFor={`notification-${key}`}>{label}</Label>
                  <Switch
                    id={`notification-${key}`}
                    checked={draft.channels[key]}
                    disabled={disabled}
                    onCheckedChange={(value) =>
                      state.editPreferences({
                        ...draft,
                        channels: { ...draft.channels, [key]: value },
                      })
                    }
                  />
                </div>
              ))}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Notificaciones en este dispositivo</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {!pushCapability && <p role="status">Comprobando navegador…</p>}
              {pushCapability?.status === "UNSUPPORTED" && (
                <p className="text-sm text-muted-foreground">
                  Este navegador no admite notificaciones Web Push.
                </p>
              )}
              {pushCapability?.status === "DENIED" && (
                <p role="alert" className="text-sm text-muted-foreground">
                  Para recibir avisos, habilita las notificaciones desde la
                  configuración del navegador y vuelve a esta página.
                </p>
              )}
              {pushCapability?.status === "SUBSCRIBED" && (
                <p role="status" className="text-sm font-medium text-primary">
                  Activo en este dispositivo
                </p>
              )}
              {pushCapability?.status === "UNSUBSCRIBED" && (
                <p role="status" className="text-sm text-muted-foreground">
                  Desactivado en este dispositivo
                </p>
              )}
              <div className="flex flex-wrap gap-3">
                {(pushCapability?.status === "AVAILABLE" ||
                  pushCapability?.status === "UNSUBSCRIBED") && (
                  <Button
                    disabled={
                      pushBusy ||
                      !state.preferences?.channels.push ||
                      state.dirty
                    }
                    onClick={async () => {
                      setPushBusy(true)
                      try {
                        const result = await requestWebPushSubscription(
                          navigator.userAgent || "Navegador web"
                        )
                        setPushCapability(result)
                        if (result.message) toast.success(result.message)
                      } catch (error) {
                        toast.error(
                          error instanceof Error
                            ? error.message
                            : "No se pudo activar Web Push."
                        )
                      } finally {
                        setPushBusy(false)
                      }
                    }}
                  >
                    Activar notificaciones en este dispositivo
                  </Button>
                )}
                {pushCapability?.status === "SUBSCRIBED" &&
                  pushCapability.subscriptionId && (
                    <Button
                      variant="outline"
                      disabled={pushBusy}
                      onClick={async () => {
                        setPushBusy(true)
                        try {
                          const result = await revokeWebPushSubscription(
                            pushCapability.subscriptionId ?? ""
                          )
                          setPushCapability(result)
                          if (result.message) toast.success(result.message)
                        } catch (error) {
                          toast.error(
                            error instanceof Error
                              ? error.message
                              : "No se pudo desactivar Web Push."
                          )
                        } finally {
                          setPushBusy(false)
                        }
                      }}
                    >
                      Desactivar en este dispositivo
                    </Button>
                  )}
              </div>
              {(!state.preferences?.channels.push || state.dirty) && (
                <p className="text-xs text-muted-foreground">
                  Activa primero el canal Push y guarda tus preferencias.
                </p>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Tipos de avisos</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {(
                [
                  ["INTERCHANGES", "Intercambios"],
                  ["POINTS", "Puntos"],
                  ["GENERAL", "General"],
                ] as const
              ).map(([key, label]) => (
                <div
                  key={key}
                  className="flex min-h-11 items-center justify-between gap-4"
                >
                  <Label htmlFor={`notification-${key}`}>{label}</Label>
                  <Switch
                    id={`notification-${key}`}
                    checked={draft.categories[key]}
                    disabled={disabled}
                    onCheckedChange={(value) =>
                      state.editPreferences({
                        ...draft,
                        categories: { ...draft.categories, [key]: value },
                      })
                    }
                  />
                </div>
              ))}
            </CardContent>
          </Card>
          <p role="status" className="text-sm">
            {state.preferencesSaving
              ? "Guardando…"
              : state.dirty
                ? "Tienes cambios sin guardar."
                : "Configuración sincronizada."}
          </p>
          <div className="flex flex-wrap gap-3">
            <Button
              disabled={disabled || !state.dirty || state.preferencesConflict}
              onClick={() => void state.savePreferences()}
            >
              Guardar preferencias
            </Button>
            {state.dirty ? (
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button variant="outline" disabled={disabled}>
                    Descartar y recargar
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>¿Descartar cambios?</AlertDialogTitle>
                    <AlertDialogDescription>
                      Tu borrador será reemplazado por la configuración
                      guardada.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Seguir editando</AlertDialogCancel>
                    <AlertDialogAction
                      onClick={() => void state.loadPreferences(true)}
                    >
                      Recargar configuración
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            ) : (
              <Button
                variant="outline"
                disabled={disabled}
                onClick={() => void state.loadPreferences(true)}
              >
                Recargar configuración
              </Button>
            )}
          </div>
        </>
      )}
      <AlertDialog
        open={blocker.state === "blocked"}
        onOpenChange={(open) => {
          if (!open && blocker.state === "blocked") blocker.reset()
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {state.preferencesSaving
                ? "Guardado en curso"
                : state.dirty
                  ? "¿Salir sin guardar?"
                  : "Preferencias guardadas"}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {state.preferencesSaving
                ? "Espera a que termine el guardado antes de salir."
                : state.dirty
                  ? "Hay cambios pendientes en tus preferencias."
                  : "Puedes continuar a la siguiente página."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Seguir editando</AlertDialogCancel>
            <AlertDialogAction
              disabled={state.preferencesSaving}
              onClick={() => {
                if (blocker.state === "blocked") {
                  state.discardPreferences()
                  blocker.proceed()
                }
              }}
            >
              Salir y descartar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  )
}

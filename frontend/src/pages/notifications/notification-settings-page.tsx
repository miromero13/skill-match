import { useEffect, useRef } from "react"
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

export function NotificationSettingsPage() {
  const state = useNotificationStore()
  const title = useRef<HTMLHeadingElement>(null)
  const version = useAuthStore(() => getAuthSessionVersion())
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

import { useEffect, useRef, useState } from "react"
import { Link } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
} from "@/components/ui/alert-dialog"
import { useNotificationStore } from "@/stores/notification-store"
import { getAuthSessionVersion, useAuthStore } from "@/stores/auth-store"
import type {
  NotificationFilters,
  NotificationItem,
} from "@/types/notification"

const filters: Record<string, NotificationFilters> = {
  all: {},
  unread: { unread: true },
  interchanges: { category: "INTERCHANGES" },
  points: { category: "POINTS" },
}
const labels = {
  all: "Todas",
  unread: "No leídas",
  interchanges: "Intercambios",
  points: "Puntos",
}
const categories = {
  INTERCHANGES: "Intercambios",
  POINTS: "Puntos",
  GENERAL: "General",
}

export function NotificationInboxPage() {
  const state = useNotificationStore()
  const [deleting, setDeleting] = useState<NotificationItem | null>(null)
  const title = useRef<HTMLHeadingElement>(null)
  const version = useAuthStore(() => getAuthSessionVersion())
  const tab = state.filters.unread
    ? "unread"
    : state.filters.category === "INTERCHANGES"
      ? "interchanges"
      : state.filters.category === "POINTS"
        ? "points"
        : "all"
  useEffect(() => {
    title.current?.focus()
    const refresh = () => {
      if (!useNotificationStore.getState().mutating)
        void useNotificationStore.getState().loadList()
    }
    refresh()
    window.addEventListener("focus", refresh)
    return () => window.removeEventListener("focus", refresh)
  }, [version])
  return (
    <section className="mx-auto w-full max-w-3xl min-w-0 space-y-5 p-4 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 ref={title} tabIndex={-1} className="text-xl font-bold">
            Bandeja de notificaciones
          </h1>
          <p className="text-sm text-muted-foreground">
            Tu historial personal de avisos.
          </p>
        </div>
        <Button asChild variant="outline">
          <Link to="/notifications/settings">Preferencias</Link>
        </Button>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button
          variant="outline"
          disabled={state.loading || state.mutating}
          onClick={() => void state.loadList()}
        >
          Actualizar
        </Button>
        <Button
          disabled={
            state.mutating ||
            state.unreadTotal === 0 ||
            Boolean(state.unreadError)
          }
          onClick={async () => {
            if (await state.markAllRead()) title.current?.focus()
          }}
        >
          Marcar todas como leídas
        </Button>
      </div>
      {state.mutationError && <p role="alert">{state.mutationError}</p>}
      <Tabs
        value={tab}
        onValueChange={(value) => {
          state.setFilters(filters[value] ?? {})
          void state.loadList(1)
        }}
      >
        <TabsList
          aria-label="Filtrar notificaciones"
          className="h-auto min-h-12 w-full flex-wrap gap-1"
        >
          {Object.entries(labels).map(([key, label]) => (
            <TabsTrigger className="min-h-10" key={key} value={key}>
              {label}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent
          value={tab}
          aria-busy={state.loading}
          className="space-y-3"
        >
          {state.loading && <p role="status">Cargando notificaciones…</p>}
          {state.listError && (
            <div role="alert">
              <p>{state.listError}</p>
              <Button
                variant="outline"
                disabled={state.loading}
                onClick={() => void state.loadList()}
              >
                Reintentar
              </Button>
            </div>
          )}
          {!state.loading && !state.listError && state.items.length === 0 && (
            <p role="status">No hay notificaciones para este filtro.</p>
          )}
          {!state.listError &&
            state.items.map((item) => (
              <Card
                key={item.id}
                size="sm"
                className={
                  item.read_at ? "" : "border border-primary bg-primary/5"
                }
              >
                <CardContent className="space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Badge variant="secondary">
                      {categories[item.category]}
                    </Badge>
                    <span className="text-xs font-medium">
                      {item.read_at ? "Leída" : "No leída"}
                    </span>
                  </div>
                  <h2 className="font-semibold [overflow-wrap:anywhere]">
                    {item.title}
                  </h2>
                  <p className="text-sm [overflow-wrap:anywhere] whitespace-pre-wrap">
                    {item.message}
                  </p>
                  <time
                    className="block text-xs text-muted-foreground"
                    dateTime={item.created_at}
                  >
                    {new Date(item.created_at).toLocaleString("es")}
                  </time>
                  <div className="flex flex-wrap gap-2">
                    {!item.read_at && (
                      <Button
                        variant="outline"
                        className="min-h-11"
                        disabled={state.mutating || state.loading}
                        aria-label={`Marcar como leída: ${item.title}`}
                        onClick={async () => {
                          if (await state.markRead(item.id))
                            title.current?.focus()
                        }}
                      >
                        Marcar como leída
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      className="min-h-11"
                      disabled={state.mutating || state.loading}
                      aria-label={`Eliminar: ${item.title}`}
                      onClick={() => setDeleting(item)}
                    >
                      Eliminar
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          <nav
            aria-label="Paginación de notificaciones"
            className="flex flex-wrap items-center justify-between gap-2"
          >
            <Button
              variant="outline"
              disabled={state.page <= 1 || state.loading || state.mutating}
              onClick={() => void state.loadList(state.page - 1)}
            >
              Anterior
            </Button>
            <p role="status" className="text-sm">
              Página {state.page} · {state.total} avisos
            </p>
            <Button
              variant="outline"
              disabled={
                state.page * 20 >= state.total ||
                state.loading ||
                state.mutating
              }
              onClick={() => void state.loadList(state.page + 1)}
            >
              Siguiente
            </Button>
          </nav>
        </TabsContent>
      </Tabs>
      <AlertDialog
        open={Boolean(deleting)}
        onOpenChange={(open) => {
          if (!open) setDeleting(null)
        }}
      >
        <AlertDialogContent
          onCloseAutoFocus={(event) => {
            event.preventDefault()
            title.current?.focus()
          }}
        >
          <AlertDialogHeader>
            <AlertDialogTitle>¿Eliminar notificación?</AlertDialogTitle>
            <AlertDialogDescription>
              Se quitará «{deleting?.title}» de tu bandeja.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                if (deleting) void state.remove(deleting.id)
              }}
            >
              Eliminar notificación
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  )
}

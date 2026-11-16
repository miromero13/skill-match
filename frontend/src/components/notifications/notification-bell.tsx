import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { Bell } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { ScrollArea } from "@/components/ui/scroll-area"
import { useNotificationStore } from "@/stores/notification-store"
import { getAuthSessionVersion, useAuthStore } from "@/stores/auth-store"
import { getNotifications } from "@/services/notification-service"
import type { NotificationItem } from "@/types/notification"

function NotificationPreview() {
  const [items, setItems] = useState<NotificationItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  const version = useAuthStore(() => getAuthSessionVersion())
  useEffect(() => {
    let active = true
    getNotifications({}, 1, 5)
      .then(
        (response) => {
          if (active) setItems(response.data)
        },
        (reason: unknown) => {
          if (active)
            setError(
              reason instanceof Error
                ? reason.message
                : "No se pudieron cargar los avisos."
            )
        }
      )
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [attempt, version])
  return (
    <>
      {loading && <p role="status">Cargando avisos…</p>}
      {error && (
        <div role="alert">
          <p>{error}</p>
          <Button
            variant="outline"
            onClick={() => {
              setLoading(true)
              setError(null)
              setAttempt(attempt + 1)
            }}
          >
            Reintentar
          </Button>
        </div>
      )}
      {!loading && !error && items.length === 0 && (
        <p>No tienes notificaciones.</p>
      )}
      {!error && (
        <ScrollArea className="max-h-[45dvh] overflow-y-auto">
          <ul className="space-y-3">
            {items.map((item) => (
              <li
                key={item.id}
                className="rounded-md border p-3 [overflow-wrap:anywhere] break-words"
              >
                <p className="font-semibold">{item.title}</p>
                <p className="text-xs text-muted-foreground">{item.message}</p>
                <p className="mt-1 text-xs">
                  {item.read_at ? "Leída" : "No leída"}
                </p>
              </li>
            ))}
          </ul>
        </ScrollArea>
      )}
    </>
  )
}

export function NotificationBell() {
  const [open, setOpen] = useState(false)
  const count = useNotificationStore((state) => state.unreadTotal)
  const error = useNotificationStore((state) => state.unreadError)
  const loadUnread = useNotificationStore((state) => state.loadUnread)
  const version = useAuthStore(() => getAuthSessionVersion())
  useEffect(() => {
    void loadUnread()
    const refresh = () => {
      if (document.visibilityState !== "hidden") void loadUnread()
    }
    window.addEventListener("focus", refresh)
    return () => window.removeEventListener("focus", refresh)
  }, [loadUnread, version])
  return (
    <Popover
      open={open}
      onOpenChange={(value) => {
        setOpen(value)
        if (value) void loadUnread()
      }}
    >
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="relative size-11 shrink-0 rounded-full"
          aria-label={
            error
              ? "Notificaciones, contador sin actualizar"
              : `Notificaciones, ${count} no leídas`
          }
        >
          <Bell className="size-5" aria-hidden="true" />
          {count > 0 && (
            <span
              aria-hidden="true"
              className="absolute top-0 right-0 rounded-full bg-destructive px-1 text-[10px] font-bold text-white"
            >
              {count > 99 ? "99+" : count}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        className="w-[calc(100vw-2rem)] max-w-sm"
        aria-label="Vista breve de notificaciones"
      >
        <h2 className="font-semibold">Notificaciones</h2>
        {error && (
          <p role="status" className="text-xs">
            {error}
          </p>
        )}
        <NotificationPreview key={version} />
        <div className="flex flex-wrap gap-2">
          <Button asChild onClick={() => setOpen(false)}>
            <Link to="/notifications">Ver bandeja</Link>
          </Button>
          <Button asChild variant="outline" onClick={() => setOpen(false)}>
            <Link to="/notifications/settings">Preferencias</Link>
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}

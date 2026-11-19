import { useEffect, useMemo, useState } from "react"
import { CalendarDays, RefreshCw } from "lucide-react"

import { SessionCard } from "@/components/sessions/session-card"
import { SessionQuotaWidget } from "@/components/sessions/session-quota-widget"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useAuthStore } from "@/stores/auth-store"
import { useExchangeSessionStore } from "@/stores/exchange-session-store"
import type { ExchangeSessionStatus } from "@/types/exchange-session"

type SessionFilter = "ALL" | ExchangeSessionStatus

export function SessionsPage() {
  const [filter, setFilter] = useState<SessionFilter>("ALL")
  const userId = useAuthStore((state) => state.user?.id)
  const items = useExchangeSessionStore((state) => state.items)
  const freeSessionsLeft = useExchangeSessionStore((state) => state.freeSessionsLeft)
  const freeSessionsLimit = useExchangeSessionStore((state) => state.freeSessionsLimit)
  const loading = useExchangeSessionStore((state) => state.loading)
  const loaded = useExchangeSessionStore((state) => state.loaded)
  const error = useExchangeSessionStore((state) => state.error)
  const pending = useExchangeSessionStore((state) => state.pending)
  const load = useExchangeSessionStore((state) => state.load)
  const accept = useExchangeSessionStore((state) => state.accept)
  const reject = useExchangeSessionStore((state) => state.reject)
  const reschedule = useExchangeSessionStore((state) => state.reschedule)
  const cancel = useExchangeSessionStore((state) => state.cancel)

  useEffect(() => {
    if (!loaded && !loading) void load()
  }, [load, loaded, loading])

  const filtered = useMemo(
    () => filter === "ALL" ? items : items.filter((session) => session.status === filter),
    [filter, items]
  )
  const blockedUntil = items
    .map((session) => session.booking_blocked_until)
    .filter((value): value is string => Boolean(value))
    .sort()
    .at(-1)

  return (
    <section className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6 sm:py-8 lg:px-8">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-semibold text-primary">Agenda de intercambios</p>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Mis sesiones</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">Revisa propuestas, confirma horarios y administra tus intercambios activos.</p>
        </div>
        <Button variant="outline" onClick={() => void load()} disabled={loading} className="w-full sm:w-auto">
          <RefreshCw aria-hidden="true" className={loading ? "animate-spin" : ""} />Actualizar
        </Button>
      </header>

      <SessionQuotaWidget freeSessionsLeft={freeSessionsLeft} freeSessionsLimit={freeSessionsLimit} />

      {blockedUntil && new Date(blockedUntil) > new Date() && (
        <Alert variant="destructive"><AlertTitle>Agendamiento temporalmente restringido</AlertTitle><AlertDescription>Puedes consultar y cancelar tus sesiones existentes. Podrás crear nuevas propuestas después del {new Intl.DateTimeFormat("es-BO", { dateStyle: "long", timeStyle: "short" }).format(new Date(blockedUntil))}.</AlertDescription></Alert>
      )}

      {freeSessionsLeft === 0 && (
        <Alert role="status" className="border-amber-300 bg-amber-50/70"><AlertTitle>No quedan sesiones gratuitas esta semana</AlertTitle><AlertDescription>El pago de sesiones adicionales se habilitará únicamente cuando esté disponible el contrato aprobado de HU-42.</AlertDescription></Alert>
      )}

      {error && !loading && (
        <Alert variant="destructive" role="alert"><AlertTitle>No pudimos cargar tus sesiones</AlertTitle><AlertDescription className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between"><span>{error}</span><Button variant="outline" size="sm" onClick={() => void load()}>Reintentar</Button></AlertDescription></Alert>
      )}

      {loading ? (
        <div role="status" aria-label="Cargando sesiones" className="grid gap-4 md:grid-cols-2">
          <span className="sr-only">Cargando sesiones</span>
          {[0, 1].map((item) => <Card key={item}><CardContent className="space-y-4 p-5"><Skeleton className="h-6 w-2/3" /><Skeleton className="h-24 w-full" /><Skeleton className="h-10 w-full" /></CardContent></Card>)}
        </div>
      ) : !error && loaded ? (
        <Tabs value={filter} onValueChange={(value) => setFilter(value as SessionFilter)}>
          <TabsList className="grid h-auto w-full grid-cols-2 gap-1 sm:grid-cols-3 lg:grid-cols-6">
            <TabsTrigger value="ALL">Todas</TabsTrigger>
            <TabsTrigger value="PENDING">Pendientes</TabsTrigger>
            <TabsTrigger value="ACCEPTED">Confirmadas</TabsTrigger>
            <TabsTrigger value="COMPLETED">Completadas</TabsTrigger>
            <TabsTrigger value="REJECTED">Rechazadas</TabsTrigger>
            <TabsTrigger value="CANCELLED">Canceladas</TabsTrigger>
          </TabsList>
          {["ALL", "PENDING", "ACCEPTED", "COMPLETED", "REJECTED", "CANCELLED"].map((value) => (
            <TabsContent key={value} value={value} className="mt-5">
              {filtered.length === 0 ? (
                <Card className="border-dashed"><CardContent className="flex min-h-56 flex-col items-center justify-center gap-3 p-6 text-center"><div className="rounded-full bg-primary/10 p-3"><CalendarDays aria-hidden="true" className="size-6 text-primary" /></div><div><p className="font-semibold">No tienes sesiones programadas.</p><p className="mt-1 text-sm text-muted-foreground">Las propuestas de tus coincidencias aparecerán aquí.</p></div></CardContent></Card>
              ) : (
                <div className="grid gap-4 xl:grid-cols-2">
                  {filtered.map((session) => (
                    <SessionCard
                      key={session.id}
                      session={session}
                      currentUserId={userId}
                      pending={Boolean(
                        pending[`status:${session.id}`] ||
                        pending[`reschedule:${session.id}`] ||
                        pending[`cancel:${session.id}`] ||
                        pending[`confirm:${session.id}`] ||
                        pending[`noshow:${session.id}`]
                      )}
                      onAccept={accept}
                      onReject={reject}
                      onReschedule={(id, startsAt, endsAt) => reschedule(id, { starts_at: startsAt, ends_at: endsAt })}
                      onCancel={cancel}
                    />
                  ))}
                </div>
              )}
            </TabsContent>
          ))}
        </Tabs>
      ) : null}
    </section>
  )
}

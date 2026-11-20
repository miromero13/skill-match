import { useEffect, useMemo, useState } from "react"
import { CalendarDays, CheckCircle2, Clock3, Video } from "lucide-react"
import { Link } from "react-router-dom"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { getMatchSessionOptions } from "@/services/match-service"
import { useExchangeSessionStore } from "@/stores/exchange-session-store"
import { useWalletStore } from "@/stores/wallet-store"
import type { CommonSessionSlot, MatchSessionOptions } from "@/types/match"

interface MatchSessionBookingProps {
  matchId: string
}

function slotKey(slot: CommonSessionSlot) {
  return `${slot.starts_at}|${slot.ends_at}|${slot.modality}`
}

function formatSlot(slot: CommonSessionSlot, timezone: string) {
  const format = new Intl.DateTimeFormat("es-BO", {
    timeZone: timezone,
    weekday: "short",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  })
  const end = new Intl.DateTimeFormat("es-BO", {
    timeZone: timezone,
    hour: "2-digit",
    minute: "2-digit",
  })
  return `${format.format(new Date(slot.starts_at))} – ${end.format(new Date(slot.ends_at))}`
}

export function MatchSessionBooking({ matchId }: MatchSessionBookingProps) {
  const create = useExchangeSessionStore((state) => state.create)
  const creating = useExchangeSessionStore((state) =>
    Boolean(state.pending.create)
  )
  const freeSessionsLeft = useExchangeSessionStore((state) => state.freeSessionsLeft)
  const quotaLoaded = useExchangeSessionStore((state) => state.loaded)
  const availableBalance = useWalletStore((state) => state.availableBalance)
  const loadBalance = useWalletStore((state) => state.loadBalance)
  const [options, setOptions] = useState<MatchSessionOptions | null>(null)
  const [directionIndex, setDirectionIndex] = useState("0")
  const [selectedSlot, setSelectedSlot] = useState("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retry, setRetry] = useState(0)
  const [created, setCreated] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    void getMatchSessionOptions(matchId, controller.signal)
      .then((response) => {
        if (controller.signal.aborted) return
        setOptions(response.data)
        const first = response.data.directions[0]?.common_slots[0]
        if (first) setSelectedSlot(slotKey(first))
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted)
          setError(
            reason instanceof Error
              ? reason.message
              : "No se pudieron cargar los horarios disponibles."
          )
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [matchId, retry])

  function retryOptions() {
    setLoading(true)
    setError(null)
    setOptions(null)
    setDirectionIndex("0")
    setSelectedSlot("")
    setCreated(false)
    setSubmitting(false)
    setRetry((value) => value + 1)
  }

  const direction = options?.directions[Number(directionIndex)]
  const slot = useMemo(
    () =>
      direction?.common_slots.find((item) => slotKey(item) === selectedSlot),
    [direction, selectedSlot]
  )
  const slotFreeSessionsLeft = slot?.free_sessions_left ?? freeSessionsLeft
  const quotaKnown = slot?.free_sessions_left !== undefined || quotaLoaded
  const requiresPoints = quotaKnown && slotFreeSessionsLeft === 0
  const pointsRequired = direction?.hourly_points_rate ?? 0
  const canPayWithPoints = Boolean(
    direction?.accepts_points && pointsRequired > 0 && availableBalance >= pointsRequired
  )

  useEffect(() => {
    if (requiresPoints) void loadBalance()
  }, [loadBalance, requiresPoints])

  function changeDirection(value: string) {
    setDirectionIndex(value)
    const first = options?.directions[Number(value)]?.common_slots[0]
    setSelectedSlot(first ? slotKey(first) : "")
  }

  async function submit() {
    if (!options || !direction || !slot || creating || submitting) return
    setSubmitting(true)
    try {
      const success = await create({
        match_id: options.match_id,
        teaching_skill_id: direction.teaching_skill_id,
        instructor_id: direction.instructor_id,
        starts_at: slot.starts_at,
        ends_at: slot.ends_at,
        timezone: slot.timezone,
        modality: slot.modality,
        payment_method: requiresPoints ? "POINTS" : "FREE",
      })
      if (success) setCreated(true)
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div
        className="space-y-3 border-t pt-4"
        role="status"
        aria-label="Cargando horarios comunes"
      >
        <Skeleton className="h-5 w-48" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-9 w-full" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-3 border-t pt-4">
        <Alert variant="destructive" role="alert">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
        <Button variant="outline" onClick={retryOptions}>
          Reintentar horarios
        </Button>
      </div>
    )
  }

  if (created) {
    return (
      <div
        className="space-y-3 rounded-xl border border-primary/30 bg-primary/5 p-4"
        role="status"
      >
        <div className="flex items-center gap-2 font-semibold">
          <CheckCircle2 className="size-5 text-primary" aria-hidden="true" />
          Sesión propuesta correctamente
        </div>
        <p className="text-sm text-muted-foreground">
          La contraparte debe aceptar el horario para confirmar la sesión.
        </p>
        <Button asChild className="w-full">
          <Link to="/sessions">Ir a Mis Intercambios</Link>
        </Button>
      </div>
    )
  }

  if (options?.booking_blocked_until) {
    return (
      <Alert variant="destructive" className="mt-4" role="alert">
        <AlertDescription>
          No puedes agendar hasta el{" "}
          {new Date(options.booking_blocked_until).toLocaleString("es-BO")}.
        </AlertDescription>
      </Alert>
    )
  }

  if (!options || options.directions.length === 0) {
    return (
      <Alert className="mt-4" role="status">
        <AlertDescription>
          No hay opciones de agendamiento disponibles para este intercambio.
        </AlertDescription>
      </Alert>
    )
  }

  return (
    <section
      className="space-y-4 border-t pt-4"
      aria-labelledby={`booking-${matchId}`}
    >
      <div>
        <h3
          id={`booking-${matchId}`}
          className="flex items-center gap-2 font-semibold"
        >
          <CalendarDays className="size-5 text-primary" aria-hidden="true" />
          Agendar sesión
        </h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Selecciona una franja común. La sesión quedará pendiente de
          aceptación.
        </p>
      </div>

      {options.directions.length > 1 ? (
        <div className="grid gap-2">
          <Label htmlFor={`booking-direction-${matchId}`}>
            Habilidad e instructor
          </Label>
          <Select
            value={directionIndex}
            onValueChange={changeDirection}
            disabled={creating || submitting}
          >
            <SelectTrigger id={`booking-direction-${matchId}`}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {options.directions.map((item, index) => (
                <SelectItem
                  key={`${item.teaching_skill_id}-${item.instructor_id}`}
                  value={String(index)}
                >
                  {item.skill_name} · {item.instructor_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ) : (
        <div className="rounded-lg border bg-muted/30 p-3 text-sm">
          <p className="font-medium">{direction?.skill_name}</p>
          <p className="text-muted-foreground">
            Instructor: {direction?.instructor_name}
          </p>
        </div>
      )}

      {direction && direction.common_slots.length > 0 ? (
        <div className="grid gap-2">
          <Label>Horario común</Label>
          <div
            className="grid max-h-56 gap-2 overflow-y-auto pr-1 sm:grid-cols-2"
            role="radiogroup"
            aria-label="Horarios comunes"
          >
            {direction.common_slots.map((item) => {
              const key = slotKey(item)
              const active = key === selectedSlot
              return (
                <Button
                  key={key}
                  type="button"
                  variant={active ? "default" : "outline"}
                  className="h-auto min-h-16 justify-start px-3 py-2 text-left whitespace-normal"
                  role="radio"
                  aria-checked={active}
                  disabled={creating || submitting}
                  onClick={() => setSelectedSlot(key)}
                >
                  <span className="grid gap-1">
                    <span className="flex items-center gap-1.5 font-medium">
                      <Clock3 className="size-4" aria-hidden="true" />
                      {formatSlot(item, options.timezone)}
                    </span>
                    <span className="flex flex-wrap gap-1.5">
                      <Badge variant={active ? "secondary" : "outline"}>
                        {item.duration_minutes} min
                      </Badge>
                      <Badge variant={active ? "secondary" : "outline"}>
                        <Video className="mr-1 size-3" aria-hidden="true" />
                        {item.modality === "VIRTUAL" ? "Virtual" : "Presencial"}
                      </Badge>
                    </span>
                  </span>
                </Button>
              )
            })}
          </div>
        </div>
      ) : (
        <Alert role="status">
          <AlertDescription>
            No hay horarios comunes disponibles durante los próximos{" "}
            {options.horizon_days} días.
          </AlertDescription>
        </Alert>
      )}

      {requiresPoints && direction && (
        <Alert
          variant={canPayWithPoints ? "default" : "destructive"}
          role="status"
        >
          <AlertDescription>
            {direction.accepts_points && pointsRequired > 0
              ? `Esta sesión requiere ${pointsRequired} SkillPoints. Tu saldo disponible es ${availableBalance} SkillPoints.`
              : "Esta oferta no admite sesiones adicionales con SkillPoints."}
          </AlertDescription>
        </Alert>
      )}

      <Button
        className="w-full"
        disabled={
          !slot ||
          creating ||
          submitting ||
          !quotaKnown ||
          (requiresPoints && !canPayWithPoints)
        }
        onClick={() => void submit()}
      >
        {creating || submitting
          ? "Agendando…"
          : requiresPoints
            ? `Agendar por ${pointsRequired} SkillPoints`
            : "Agendar sesión gratuita"}
      </Button>
    </section>
  )
}

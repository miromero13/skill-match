import { useState } from "react"
import { CalendarDays, Clock3, MapPin, Monitor } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { localToUtc } from "@/components/sessions/session-booking-form"
import { SessionCalendarExportDialog } from "@/components/sessions/session-calendar-export"
import type { ExchangeSession } from "@/types/exchange-session"

interface Props { session: ExchangeSession; currentUserId?: string; pending?: boolean; onAccept: (id: string) => Promise<boolean>; onReject: (id: string) => Promise<boolean>; onReschedule: (id: string, startsAt: string, endsAt: string) => Promise<boolean>; onCancel: (id: string, reason: string) => Promise<boolean> }
const copy = { PENDING: "Pendiente", ACCEPTED: "Confirmada", REJECTED: "Rechazada", CANCELLED: "Cancelada" } as const
const variants = { PENDING: "secondary", ACCEPTED: "default", REJECTED: "outline", CANCELLED: "destructive" } as const
const date = (value: string, timezone: string) => new Intl.DateTimeFormat("es-BO", { timeZone: timezone, weekday: "long", day: "numeric", month: "long" }).format(new Date(value))
const time = (value: string, timezone: string) => new Intl.DateTimeFormat("es-BO", { timeZone: timezone, hour: "2-digit", minute: "2-digit" }).format(new Date(value))

export function SessionCard({ session, currentUserId, pending = false, onAccept, onReject, onReschedule, onCancel }: Props) {
  const [cancelOpen, setCancelOpen] = useState(false); const [rescheduleOpen, setRescheduleOpen] = useState(false)
  const [reason, setReason] = useState(""); const [startsAt, setStartsAt] = useState(""); const [endsAt, setEndsAt] = useState(""); const [error, setError] = useState<string | null>(null)
  const canAnswer = session.status === "PENDING" && session.created_by_id !== currentUserId
  const canModify = session.status === "PENDING" || session.status === "ACCEPTED"
  const cancel = async () => { const value = reason.trim(); if (value.length < 10 || value.length > 500) { setError("El motivo debe tener entre 10 y 500 caracteres."); return } if (await onCancel(session.id, value)) { setCancelOpen(false); setReason(""); setError(null) } }
  const reschedule = async () => { const start = localToUtc(startsAt, session.timezone); const end = localToUtc(endsAt, session.timezone); const duration = start && end ? (end.getTime() - start.getTime()) / 60_000 : 0; if (!start || !end || duration < 1 || duration > 60) { setError("La sesión debe durar entre 1 y 60 minutos."); return } if (await onReschedule(session.id, start.toISOString(), end.toISOString())) { setRescheduleOpen(false); setError(null) } }
  return <Card className="overflow-hidden shadow-sm">
    <CardHeader className="flex-row items-start justify-between gap-3 bg-muted/20"><div><CardTitle className="text-base sm:text-lg">Sesión de intercambio</CardTitle><p className="text-xs text-muted-foreground">Referencia {session.id.slice(0, 8)}</p></div><Badge variant={variants[session.status]}>{copy[session.status]}</Badge></CardHeader>
    <CardContent className="grid gap-4 pt-5"><div className="grid gap-3 rounded-xl border p-4 sm:grid-cols-2"><div className="flex gap-3"><CalendarDays aria-hidden="true" className="size-4 text-primary" /><div><p className="text-xs text-muted-foreground">Fecha</p><p className="font-medium capitalize">{date(session.starts_at, session.timezone)}</p></div></div><div className="flex gap-3"><Clock3 aria-hidden="true" className="size-4 text-primary" /><div><p className="text-xs text-muted-foreground">Horario</p><p className="font-medium">{time(session.starts_at, session.timezone)} – {time(session.ends_at, session.timezone)}</p></div></div><div className="flex gap-3 sm:col-span-2">{session.modality === "VIRTUAL" ? <Monitor aria-hidden="true" className="size-4 text-primary" /> : <MapPin aria-hidden="true" className="size-4 text-primary" />}<div><p className="text-xs text-muted-foreground">Modalidad</p><p className="font-medium">{session.modality === "VIRTUAL" ? "Virtual" : "Presencial"}</p></div></div></div>{session.cancellation_reason && <Alert><AlertDescription><strong>Motivo de cancelación:</strong> {session.cancellation_reason}</AlertDescription></Alert>}</CardContent>
    {canModify && <CardFooter className="flex flex-col-reverse gap-2 border-t p-4 sm:flex-row sm:justify-end">
      {session.status === "ACCEPTED" && <SessionCalendarExportDialog sessionId={session.id} />}
      <Dialog open={cancelOpen} onOpenChange={(open) => { setCancelOpen(open); setError(null) }}><DialogTrigger asChild><Button variant="outline" className="w-full sm:w-auto">Cancelar sesión</Button></DialogTrigger><DialogContent><DialogHeader><DialogTitle>Cancelar sesión</DialogTitle><DialogDescription>Indica el motivo. Esta acción quedará auditada.</DialogDescription></DialogHeader><div className="grid gap-2"><Label htmlFor={`cancel-${session.id}`}>Motivo de cancelación</Label><Textarea id={`cancel-${session.id}`} value={reason} onChange={(event) => setReason(event.target.value)} maxLength={500} /></div>{error && <Alert variant="destructive" role="alert"><AlertDescription>{error}</AlertDescription></Alert>}<DialogFooter><Button variant="outline" onClick={() => setCancelOpen(false)}>Volver</Button><Button variant="destructive" onClick={cancel} disabled={pending}>Confirmar cancelación</Button></DialogFooter></DialogContent></Dialog>
      <Dialog open={rescheduleOpen} onOpenChange={(open) => { setRescheduleOpen(open); setError(null) }}><DialogTrigger asChild><Button variant="outline" className="w-full sm:w-auto">Proponer otro horario</Button></DialogTrigger><DialogContent><DialogHeader><DialogTitle>Proponer otro horario</DialogTitle><DialogDescription>La sesión volverá a pendiente hasta que la contraparte responda.</DialogDescription></DialogHeader><div className="grid gap-4 sm:grid-cols-2"><div className="grid gap-2"><Label htmlFor={`start-${session.id}`}>Nuevo inicio</Label><Input id={`start-${session.id}`} type="datetime-local" value={startsAt} onChange={(event) => setStartsAt(event.target.value)} /></div><div className="grid gap-2"><Label htmlFor={`end-${session.id}`}>Nuevo fin</Label><Input id={`end-${session.id}`} type="datetime-local" value={endsAt} onChange={(event) => setEndsAt(event.target.value)} /></div></div>{error && <Alert variant="destructive" role="alert"><AlertDescription>{error}</AlertDescription></Alert>}<DialogFooter><Button variant="outline" onClick={() => setRescheduleOpen(false)}>Volver</Button><Button onClick={reschedule} disabled={pending}>Enviar propuesta</Button></DialogFooter></DialogContent></Dialog>
      {canAnswer && <><Button variant="outline" className="w-full sm:w-auto" onClick={() => onReject(session.id)} disabled={pending}>Rechazar</Button><Button className="w-full sm:w-auto" onClick={() => onAccept(session.id)} disabled={pending}>Aceptar propuesta</Button></>}
    </CardFooter>}
  </Card>
}

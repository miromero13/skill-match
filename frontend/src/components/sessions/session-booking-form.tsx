import { useState, type FormEvent } from "react"
import { CalendarDays } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import type { ExchangeSessionCreate, ExchangeSessionModality } from "@/types/exchange-session"

interface Props {
  matchId: string; teachingSkillId: string; instructorId: string; timezone: string; disabled?: boolean
  onSubmit: (payload: ExchangeSessionCreate) => Promise<boolean> | boolean
}

export function localToUtc(value: string, timezone: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value)
  if (!match) return null
  const desired = Date.UTC(+match[1], +match[2] - 1, +match[3], +match[4], +match[5])
  const formatter = new Intl.DateTimeFormat("en-CA", { timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" })
  let result = desired
  for (let attempt = 0; attempt < 2; attempt++) {
    const parts = Object.fromEntries(formatter.formatToParts(new Date(result)).map((part) => [part.type, part.value]))
    const represented = Date.UTC(+parts.year, +parts.month - 1, +parts.day, +parts.hour, +parts.minute)
    result += desired - represented
  }
  return new Date(result)
}

export function SessionBookingForm({ matchId, teachingSkillId, instructorId, timezone, disabled = false, onSubmit }: Props) {
  const [startsAt, setStartsAt] = useState("")
  const [endsAt, setEndsAt] = useState("")
  const [modality, setModality] = useState<ExchangeSessionModality>("VIRTUAL")
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const start = localToUtc(startsAt, timezone); const end = localToUtc(endsAt, timezone)
    const duration = start && end ? (end.getTime() - start.getTime()) / 60_000 : 0
    if (!start || !end || duration < 1 || duration > 60) { setError("La sesión debe durar entre 1 y 60 minutos."); return }
    setError(null); setSubmitting(true)
    try { await onSubmit({ match_id: matchId, teaching_skill_id: teachingSkillId, instructor_id: instructorId, starts_at: start.toISOString(), ends_at: end.toISOString(), timezone, modality }) }
    finally { setSubmitting(false) }
  }
  return (
    <Card className="border-primary/20 shadow-sm"><CardHeader><CardTitle className="flex items-center gap-2 text-lg"><CalendarDays aria-hidden="true" className="size-5 text-primary" />Proponer horario</CardTitle><CardDescription>Elige una franja común de hasta 60 minutos.</CardDescription></CardHeader><CardContent>
      <form className="grid gap-4" onSubmit={submit}>
        <div className="grid gap-4 sm:grid-cols-2"><div className="grid gap-2"><Label htmlFor="session-start">Inicio</Label><Input id="session-start" type="datetime-local" value={startsAt} onChange={(event) => setStartsAt(event.target.value)} disabled={disabled || submitting} required /></div><div className="grid gap-2"><Label htmlFor="session-end">Fin</Label><Input id="session-end" type="datetime-local" value={endsAt} onChange={(event) => setEndsAt(event.target.value)} disabled={disabled || submitting} required /></div></div>
        <div className="grid gap-2"><Label htmlFor="session-modality">Modalidad</Label><Select value={modality} onValueChange={(value: ExchangeSessionModality) => setModality(value)} disabled={disabled || submitting}><SelectTrigger id="session-modality" aria-label="Modalidad"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="VIRTUAL">Virtual</SelectItem><SelectItem value="PRESENCIAL">Presencial</SelectItem></SelectContent></Select></div>
        {error && <Alert variant="destructive" role="alert"><AlertDescription>{error}</AlertDescription></Alert>}
        <Button type="submit" className="w-full sm:w-auto sm:justify-self-end" disabled={disabled || submitting}>{submitting ? "Agendando…" : "Agendar sesión"}</Button>
      </form>
    </CardContent></Card>
  )
}

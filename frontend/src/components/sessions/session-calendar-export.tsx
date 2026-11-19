import { useEffect, useRef, useState } from "react"
import { CalendarPlus, Download, ExternalLink } from "lucide-react"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
import { getSessionCalendarExport } from "@/services/exchange-session-service"
import type { SessionCalendarExport } from "@/types/exchange-session"

interface SessionCalendarExportProps {
  sessionId: string
}

export function downloadCalendarFile(data: SessionCalendarExport) {
  const blob = new Blob([data.ics_content], { type: data.content_type })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = data.filename
  anchor.click()
  URL.revokeObjectURL(url)
}

export function SessionCalendarExportDialog({ sessionId }: SessionCalendarExportProps) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<SessionCalendarExport | null>(null)
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const controller = useRef<AbortController | null>(null)

  useEffect(() => () => controller.current?.abort(), [])

  async function load() {
    if (loading) return
    controller.current?.abort()
    const request = new AbortController()
    controller.current = request
    setLoading(true)
    setData(null)
    setMessage("")
    setError("")
    try {
      const response = await getSessionCalendarExport(sessionId, request.signal)
      if (!request.signal.aborted) {
        setData(response.data)
        setMessage(response.message)
      }
    } catch (reason) {
      if (!request.signal.aborted)
        setError(
          reason instanceof Error
            ? reason.message
            : "No se pudo preparar la exportación de calendario."
        )
    } finally {
      if (!request.signal.aborted) setLoading(false)
    }
  }

  function changeOpen(next: boolean) {
    setOpen(next)
    if (next) void load()
    else controller.current?.abort()
  }

  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" className="w-full sm:w-auto">
          <CalendarPlus aria-hidden="true" />
          Añadir al calendario
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Añadir sesión al calendario</DialogTitle>
          <DialogDescription>
            Descarga un archivo compatible o abre un evento nuevo en Google Calendar. No se
            conectará ni sincronizará tu cuenta.
          </DialogDescription>
        </DialogHeader>

        {loading && (
          <div className="space-y-3" role="status" aria-label="Preparando calendario">
            <Skeleton className="h-5 w-3/4" />
            <Skeleton className="h-10 w-full" />
          </div>
        )}
        {error && (
          <div className="space-y-3">
            <Alert variant="destructive" role="alert">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
            <Button variant="outline" onClick={() => void load()} disabled={loading}>
              Reintentar
            </Button>
          </div>
        )}
        {data && (
          <Alert role="status">
            <AlertDescription>{message}</AlertDescription>
          </Alert>
        )}

        <DialogFooter className="flex-col gap-2 sm:flex-row">
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cerrar
          </Button>
          <Button
            variant="outline"
            disabled={!data || loading}
            onClick={() => data && downloadCalendarFile(data)}
          >
            <Download aria-hidden="true" />
            Descargar .ics
          </Button>
          <Button
            disabled={!data || loading}
            onClick={() =>
              data && window.open(data.google_calendar_url, "_blank", "noopener,noreferrer")
            }
          >
            <ExternalLink aria-hidden="true" />
            Abrir Google Calendar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

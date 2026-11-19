import { useState } from "react"
import { AlertTriangle, UserX } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
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
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { useExchangeSessionStore } from "@/stores/exchange-session-store"
import type { ExchangeSession } from "@/types/exchange-session"

interface Props {
  session: ExchangeSession
  trigger?: React.ReactNode
}

export function SessionNoShowDialog({ session, trigger }: Props) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const reportNoShow = useExchangeSessionStore((state) => state.reportNoShow)

  const handleSubmit = async () => {
    const trimmed = reason.trim()
    if (trimmed.length < 10 || trimmed.length > 500) {
      setError("El motivo de inasistencia debe tener entre 10 y 500 caracteres.")
      return
    }

    setLoading(true)
    setError(null)
    try {
      const success = await reportNoShow(session.id, {
        request_key: crypto.randomUUID(),
        reason: trimmed,
      })

      if (success) {
        setOpen(false)
        setReason("")
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(val) => { setOpen(val); setError(null) }}>
      <DialogTrigger asChild>
        {trigger || (
          <Button variant="outline" className="w-full text-destructive hover:bg-destructive/10 sm:w-auto">
            <UserX className="mr-2 size-4" />
            Reportar inasistencia
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-destructive">
            <UserX className="size-5" />
            Reportar inasistencia injustificada
          </DialogTitle>
          <DialogDescription>
            Si la contraparte no asistió ni se comunicó durante el horario pautado, puedes registrar un reporte de inasistencia.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-2">
          <Alert variant="destructive" className="bg-destructive/5 text-destructive">
            <AlertTriangle className="size-4" />
            <AlertTitle className="font-semibold">Acción auditable</AlertTitle>
            <AlertDescription className="text-xs">
              Este reporte quedará registrado formalmente en la bitácora y será revisado dentro del sistema de confianza y reputación.
            </AlertDescription>
          </Alert>

          <div className="grid gap-2">
            <div className="flex justify-between items-center">
              <Label htmlFor={`noshow-reason-${session.id}`} className="font-medium">
                Motivo de la inasistencia
              </Label>
              <span className="text-xs text-muted-foreground">{reason.trim().length}/500</span>
            </div>
            <Textarea
              id={`noshow-reason-${session.id}`}
              placeholder="Describe lo sucedido (ej: La contraparte no se conectó al enlace ni respondió a los mensajes tras 30 minutos de espera)..."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              maxLength={500}
              rows={4}
            />
            <p className="text-xs text-muted-foreground">Mínimo 10 caracteres, máximo 500.</p>
          </div>

          {error && (
            <Alert variant="destructive" role="alert">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="outline" onClick={() => setOpen(false)} disabled={loading}>
            Cancelar
          </Button>
          <Button
            variant="destructive"
            onClick={handleSubmit}
            disabled={loading}
          >
            {loading ? "Enviando reporte..." : "Confirmar reporte"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

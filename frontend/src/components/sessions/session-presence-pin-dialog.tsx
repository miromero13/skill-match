import { useState } from "react"
import { KeyRound, ShieldCheck } from "lucide-react"

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
import { getSessionPresencePin } from "@/services/exchange-session-service"
import type { SessionPresencePinResponse } from "@/types/exchange-session"

interface Props {
  sessionId: string
  trigger?: React.ReactNode
}

export function SessionPresencePinDialog({ sessionId, trigger }: Props) {
  const [open, setOpen] = useState(false)
  const [pinData, setPinData] = useState<SessionPresencePinResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleOpen = async (nextOpen: boolean) => {
    setOpen(nextOpen)
    if (nextOpen && !pinData && !loading) {
      setLoading(true)
      setError(null)
      try {
        const resp = await getSessionPresencePin(sessionId)
        setPinData(resp.data)
      } catch (err) {
        setError(err instanceof Error ? err.message : "No se pudo obtener el PIN de presencia.")
      } finally {
        setLoading(false)
      }
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpen}>
      <DialogTrigger asChild>
        {trigger || (
          <Button variant="outline" size="sm" className="w-full sm:w-auto">
            <KeyRound className="mr-2 size-4 text-primary" />
            Mi PIN presencial
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="max-w-sm text-center">
        <DialogHeader className="items-center text-center">
          <div className="mx-auto rounded-full bg-primary/10 p-3">
            <KeyRound className="size-6 text-primary" />
          </div>
          <DialogTitle className="text-xl">Tu PIN de presencia</DialogTitle>
          <DialogDescription>
            Comparte este código de 4 dígitos exclusivamente con tu contraparte al momento del encuentro presencial.
          </DialogDescription>
        </DialogHeader>

        <div className="py-4">
          {loading ? (
            <div className="py-6 text-sm text-muted-foreground">Generando PIN seguro...</div>
          ) : error ? (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : pinData ? (
            <div className="flex flex-col items-center gap-3">
              <div className="rounded-xl border border-primary/30 bg-muted/40 px-6 py-4">
                <span className="font-mono text-4xl font-extrabold tracking-widest text-primary">
                  {pinData.presence_pin}
                </span>
              </div>
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <ShieldCheck className="size-3.5 text-emerald-600" />
                Válido hasta {new Intl.DateTimeFormat("es-BO", { timeStyle: "short", dateStyle: "short" }).format(new Date(pinData.expires_at))}
              </div>
            </div>
          ) : null}
        </div>

        <DialogFooter className="sm:justify-center">
          <Button variant="outline" onClick={() => setOpen(false)} className="w-full sm:w-auto">
            Cerrar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

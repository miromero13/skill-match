import { useState } from "react"
import { CheckCircle2, Clock, KeyRound, ListChecks } from "lucide-react"

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
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useExchangeSessionStore } from "@/stores/exchange-session-store"
import type { ExchangeSession } from "@/types/exchange-session"

interface Props {
  session: ExchangeSession
  trigger?: React.ReactNode
}

export function SessionConfirmDialog({ session, trigger }: Props) {
  const [open, setOpen] = useState(false)
  const [minutes, setMinutes] = useState(60)
  const [topicsInput, setTopicsInput] = useState("")
  const [presencePin, setPresencePin] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const confirmSession = useExchangeSessionStore((state) => state.confirmSession)

  const handleSubmit = async () => {
    setError(null)
    if (minutes < 1 || minutes > 60) {
      setError("La duración efectiva debe estar entre 1 y 60 minutos.")
      return
    }

    if (session.modality === "PRESENCIAL") {
      const pin = presencePin.trim()
      if (pin.length !== 4 || !/^\d{4}$/.test(pin)) {
        setError("Debes ingresar el PIN de presencia de 4 dígitos proporcionado por la contraparte.")
        return
      }
    }

    const topics = topicsInput
      .split(",")
      .map((t) => t.trim())
      .filter((t) => t.length > 0)

    if (topics.length > 10) {
      setError("No puedes registrar más de 10 temas abordados.")
      return
    }

    setLoading(true)
    try {
      const success = await confirmSession(session.id, {
        request_key: crypto.randomUUID(),
        actual_minutes: minutes,
        topics: topics.length > 0 ? topics : ["Intercambio de habilidades"],
        presence_pin: session.modality === "PRESENCIAL" ? presencePin.trim() : undefined,
      })

      if (success) {
        setOpen(false)
        setTopicsInput("")
        setPresencePin("")
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(val) => { setOpen(val); setError(null) }}>
      <DialogTrigger asChild>
        {trigger || (
          <Button className="w-full sm:w-auto">
            <CheckCircle2 className="mr-2 size-4" />
            Confirmar sesión
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <CheckCircle2 className="size-5 text-primary" />
            Confirmación de sesión realizada
          </DialogTitle>
          <DialogDescription>
            Indica los minutos cumplidos y los temas abordados. La sesión se completará cuando ambas partes confirmen la misma duración.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-2">
          <div className="grid gap-2">
            <Label htmlFor={`minutes-${session.id}`} className="flex items-center gap-1.5 font-medium">
              <Clock className="size-4 text-muted-foreground" />
              Minutos efectivos cumplidos (1 a 60)
            </Label>
            <div className="flex items-center gap-2">
              <Input
                id={`minutes-${session.id}`}
                type="number"
                min={1}
                max={60}
                value={minutes}
                onChange={(e) => setMinutes(Math.max(1, Math.min(60, Number(e.target.value) || 1)))}
                className="w-28 text-center text-base font-semibold"
              />
              <div className="flex gap-1.5">
                {[30, 45, 60].map((quick) => (
                  <Button
                    key={quick}
                    type="button"
                    variant={minutes === quick ? "default" : "outline"}
                    size="sm"
                    onClick={() => setMinutes(quick)}
                  >
                    {quick}m
                  </Button>
                ))}
              </div>
            </div>
          </div>

          <div className="grid gap-2">
            <Label htmlFor={`topics-${session.id}`} className="flex items-center gap-1.5 font-medium">
              <ListChecks className="size-4 text-muted-foreground" />
              Temas abordados (separados por coma)
            </Label>
            <Input
              id={`topics-${session.id}`}
              placeholder="Ej: Fundamentos, Práctica en vivo, Dudas"
              value={topicsInput}
              onChange={(e) => setTopicsInput(e.target.value)}
              maxLength={250}
            />
            <p className="text-xs text-muted-foreground">Opcional. Máximo 10 temas de 120 caracteres cada uno.</p>
          </div>

          {session.modality === "PRESENCIAL" && (
            <div className="grid gap-2 rounded-lg border border-primary/20 bg-primary/5 p-3.5">
              <Label htmlFor={`pin-${session.id}`} className="flex items-center gap-1.5 font-medium text-foreground">
                <KeyRound className="size-4 text-primary" />
                PIN presencial de la contraparte
              </Label>
              <Input
                id={`pin-${session.id}`}
                placeholder="4 dígitos (ej: 7492)"
                value={presencePin}
                onChange={(e) => setPresencePin(e.target.value.replace(/\D/g, "").slice(0, 4))}
                maxLength={4}
                className="w-36 tracking-widest text-center text-lg font-bold"
              />
              <p className="text-xs text-muted-foreground">
                Pide a tu contraparte su PIN de 4 dígitos para verificar su presencia mutua.
              </p>
            </div>
          )}

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
          <Button onClick={handleSubmit} disabled={loading}>
            {loading ? "Confirmando..." : "Confirmar intercambio"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

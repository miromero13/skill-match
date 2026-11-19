import { Clock3 } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"

interface Props { freeSessionsLeft: number; freeSessionsLimit: number }

export function SessionQuotaWidget({ freeSessionsLeft, freeSessionsLimit }: Props) {
  const exhausted = freeSessionsLeft === 0
  return (
    <Alert role="status" className={exhausted ? "border-amber-300 bg-amber-50/70" : "border-primary/30 bg-primary/5"}>
      <Clock3 aria-hidden="true" className={exhausted ? "text-amber-700" : "text-primary"} />
      <AlertTitle>{exhausted ? "Cupo semanal agotado" : "Tu cupo de sesiones"}</AlertTitle>
      <AlertDescription>Sesiones gratuitas restantes esta semana: {freeSessionsLeft}/{freeSessionsLimit} (máx. 1h c/u)</AlertDescription>
    </Alert>
  )
}

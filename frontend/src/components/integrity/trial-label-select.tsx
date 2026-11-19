import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

/** Behaviours recorded while tuning the integrity thresholds (DEV only); the backend report groups windows by them. */
export const TRIAL_LABELS = [
  "normal",
  "mirando_abajo",
  "mirando_costado",
  "mirando_arriba",
  "ojos_abajo",
  "boca_tapada",
  "cara_tapada",
  "camara_tapada",
  "dos_personas",
  "otra_voz",
  "audio_dispositivo",
  "hablando_yo",
] as const

export type TrialLabel = (typeof TRIAL_LABELS)[number]

const isTrialLabel = (value: string): value is TrialLabel => TRIAL_LABELS.some((label) => label === value)

interface TrialLabelSelectProps {
  value: TrialLabel
  onChange: (value: TrialLabel) => void
}

export function TrialLabelSelect({ value, onChange }: TrialLabelSelectProps) {
  return (
    <div className="space-y-1">
      <Label htmlFor="trial-label">Etiqueta de prueba</Label>
      <Select value={value} onValueChange={(next) => isTrialLabel(next) && onChange(next)}>
        <SelectTrigger id="trial-label" className="w-full sm:w-64">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {TRIAL_LABELS.map((label) => (
            <SelectItem key={label} value={label}>
              {label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <p className="text-xs text-muted-foreground">Solo desarrollo: se registra con cada ventana para afinar umbrales.</p>
    </div>
  )
}

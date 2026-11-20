/**
 * Editor móvil táctil de horarios y disponibilidad semanal (HU-13 / Mobile UX).
 * Sustituye la matriz pesada de escritorio por un selector de días horizontal (Day-Strip)
 * con lista vertical de franjas horarias, presets de un toque y guardado reactivo.
 */
import { useEffect, useState } from "react"
import {
  Calendar,
  Clock,
  Copy,
  Plus,
  Save,
  Trash2,
  Zap,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useProfileStore } from "@/stores/profile-store"
import type { AvailabilitySlotInput, ExchangeModality } from "@/types/profile"
import { toast } from "sonner"

const DAYS = [
  { index: 0, name: "Lunes", short: "Lun" },
  { index: 1, name: "Martes", short: "Mar" },
  { index: 2, name: "Miércoles", short: "Mié" },
  { index: 3, name: "Jueves", short: "Jue" },
  { index: 4, name: "Viernes", short: "Vie" },
  { index: 5, name: "Sábado", short: "Sáb" },
  { index: 6, name: "Domingo", short: "Dom" },
]

const TIME_OPTIONS = [
  "07:00", "07:30", "08:00", "08:30", "09:00", "09:30", "10:00", "10:30",
  "11:00", "11:30", "12:00", "12:30", "13:00", "13:30", "14:00", "14:30",
  "15:00", "15:30", "16:00", "16:30", "17:00", "17:30", "18:00", "18:30",
  "19:00", "19:30", "20:00", "20:30", "21:00", "21:30", "22:00"
]

export function MobileAvailabilityEditor({ onSaved }: { onSaved?: () => void } = {}) {
  const { availabilitySlots, isSavingAvailability, loadAvailability, saveAvailability } =
    useProfileStore()

  const [activeDayIndex, setActiveDayIndex] = useState<number>(0)
  const [draftSlots, setDraftSlots] = useState<AvailabilitySlotInput[]>([])

  // Estado para agregar franja horaria nueva
  const [fromTime, setFromTime] = useState<string>("09:00")
  const [toTime, setToTime] = useState<string>("13:00")
  const [modality, setModality] = useState<ExchangeModality>("BOTH")

  useEffect(() => {
    if (availabilitySlots.length === 0) {
      loadAvailability()
    }
  }, [availabilitySlots.length, loadAvailability])

  useEffect(() => {
    setDraftSlots(
      availabilitySlots.map((s) => ({
        day_of_week: s.day_of_week,
        start_time: s.start_time,
        end_time: s.end_time,
        is_enabled: s.is_enabled,
        modality: s.modality || "BOTH",
      }))
    )
  }, [availabilitySlots])

  // Franjas del día actualmente seleccionado
  const currentDaySlots = draftSlots.filter(
    (s) => s.day_of_week === activeDayIndex && s.is_enabled
  )

  // Función para agregar franja al día activo
  const handleAddSlot = () => {
    if (fromTime >= toTime) {
      toast.error("Rango inválido", {
        description: "La hora de inicio debe ser anterior a la hora de fin.",
      })
      return
    }

    // Evitar solapamientos idénticos
    const exists = currentDaySlots.some(
      (s) => s.start_time === fromTime && s.end_time === toTime
    )
    if (exists) {
      toast.error("Franja existente", {
        description: "Esta franja ya está agregada para este día.",
      })
      return
    }

    setDraftSlots([
      ...draftSlots,
      {
        day_of_week: activeDayIndex,
        start_time: fromTime,
        end_time: toTime,
        is_enabled: true,
        modality,
      },
    ])
    toast.success("Franja agregada", {
      description: `Agregado ${fromTime} - ${toTime} para el ${DAYS[activeDayIndex].name}.`,
    })
  }

  // Eliminar franja
  const handleRemoveSlot = (indexInCurrent: number) => {
    const slotToRemove = currentDaySlots[indexInCurrent]
    setDraftSlots(
      draftSlots.filter(
        (s) =>
          !(
            s.day_of_week === slotToRemove.day_of_week &&
            s.start_time === slotToRemove.start_time &&
            s.end_time === slotToRemove.end_time
          )
      )
    )
  }

  // Presets Rápidos
  const handleApplyWorkday = () => {
    // Establecer 09:00 - 18:00 para el día actual
    const otherDays = draftSlots.filter((s) => s.day_of_week !== activeDayIndex)
    setDraftSlots([
      ...otherDays,
      {
        day_of_week: activeDayIndex,
        start_time: "09:00",
        end_time: "18:00",
        is_enabled: true,
        modality: "BOTH",
      },
    ])
    toast.success("Preset aplicado", {
      description: `Jornada laboral (09:00 - 18:00) asignada a ${DAYS[activeDayIndex].name}.`,
    })
  }

  const handleCopyToWeekdays = () => {
    if (currentDaySlots.length === 0) {
      toast.error("Día vacío", {
        description: "Configura primero al menos una franja en este día antes de copiar.",
      })
      return
    }
    const weekdays = [0, 1, 2, 3, 4]
    const weekendSlots = draftSlots.filter((s) => s.day_of_week === 5 || s.day_of_week === 6)
    const newWeekdaySlots: AvailabilitySlotInput[] = []

    weekdays.forEach((dayIdx) => {
      currentDaySlots.forEach((slot) => {
        newWeekdaySlots.push({
          day_of_week: dayIdx,
          start_time: slot.start_time,
          end_time: slot.end_time,
          is_enabled: true,
          modality: slot.modality,
        })
      })
    })

    setDraftSlots([...weekendSlots, ...newWeekdaySlots])
    toast.success("Copiado exitoso", {
      description: `Los horarios de ${DAYS[activeDayIndex].name} se replicaron de Lunes a Viernes.`,
    })
  }

  const handleClearDay = () => {
    setDraftSlots(draftSlots.filter((s) => s.day_of_week !== activeDayIndex))
    toast.info("Día libre", {
      description: `Se eliminaron las franjas de ${DAYS[activeDayIndex].name}.`,
    })
  }

  // Guardar en backend
  const handleSaveAll = async () => {
    const success = await saveAvailability({
      slots: draftSlots,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
    })
    if (success) {
      toast.success("Horarios guardados", {
        description: "Tu disponibilidad semanal fue actualizada exitosamente.",
      })
      onSaved?.()
    }
  }

  return (
    <Card className="border-border/80 shadow-xs">
      <CardHeader className="pb-3 space-y-1">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-bold flex items-center gap-2">
            <Calendar className="size-4 text-primary" />
            Agenda y Horarios Semanales
          </CardTitle>
          <Badge variant="outline" className="text-2xs font-normal">
            Mobile UX
          </Badge>
        </div>
        <CardDescription className="text-xs">
          Selecciona el día y configura los intervalos donde estás disponible para trueques pedagógicos.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4 pt-1">
        {/* Selector Horizontal de Días (Day-Strip) */}
        <div className="space-y-1.5">
          <Label className="text-2xs font-bold uppercase tracking-wider text-muted-foreground">
            Día de la semana
          </Label>
          <div className="grid grid-cols-7 gap-1 bg-muted/40 p-1 rounded-xl border border-border/50">
            {DAYS.map((day) => {
              const isActive = activeDayIndex === day.index
              const hasSlots = draftSlots.some(
                (s) => s.day_of_week === day.index && s.is_enabled
              )
              return (
                <button
                  key={day.index}
                  type="button"
                  onClick={() => setActiveDayIndex(day.index)}
                  className={`flex flex-col items-center justify-center py-2 px-1 rounded-lg transition-all text-center relative ${
                    isActive
                      ? "bg-primary text-primary-foreground font-bold shadow-xs scale-102"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted"
                  }`}
                >
                  <span className="text-xs">{day.short}</span>
                  {hasSlots && (
                    <span
                      className={`size-1.5 rounded-full mt-1 ${
                        isActive ? "bg-white" : "bg-emerald-500"
                      }`}
                    />
                  )}
                </button>
              )
            })}
          </div>
        </div>

        {/* Franjas Activas del Día Seleccionado */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs font-semibold text-muted-foreground">
            <span>Franjas para {DAYS[activeDayIndex].name}</span>
            <span className="text-2xs text-foreground font-bold">
              {currentDaySlots.length} {currentDaySlots.length === 1 ? "franja" : "franjas"}
            </span>
          </div>

          {currentDaySlots.length === 0 ? (
            <div className="p-4 rounded-xl border border-dashed text-center text-xs text-muted-foreground bg-muted/20">
              No tienes disponibilidad configurada para el {DAYS[activeDayIndex].name}.
              <br />
              <span className="text-2xs text-muted-foreground/80">
                (Aparecerás como no disponible este día)
              </span>
            </div>
          ) : (
            <div className="space-y-2">
              {currentDaySlots.map((slot, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-2.5 rounded-xl border border-border bg-card shadow-2xs text-xs"
                >
                  <div className="flex items-center gap-2">
                    <Clock className="size-3.5 text-primary" />
                    <span className="font-bold text-foreground">
                      {slot.start_time} - {slot.end_time}
                    </span>
                    <Badge variant="secondary" className="text-2xs px-2 py-0">
                      {slot.modality === "BOTH"
                        ? "Ambas"
                        : slot.modality === "VIRTUAL"
                        ? "Virtual"
                        : "Presencial"}
                    </Badge>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-7 text-destructive hover:bg-destructive/10"
                    onClick={() => handleRemoveSlot(idx)}
                    aria-label="Eliminar franja"
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Añadir Nueva Franja */}
        <div className="p-3 rounded-xl border border-border bg-muted/20 space-y-3">
          <Label className="text-xs font-bold text-foreground flex items-center gap-1.5">
            <Plus className="size-3.5 text-primary" />
            Agregar Nueva Franja Horaria
          </Label>

          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label className="text-2xs text-muted-foreground">Desde</Label>
              <Select value={fromTime} onValueChange={setFromTime}>
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue placeholder="Desde" />
                </SelectTrigger>
                <SelectContent className="max-h-48">
                  {TIME_OPTIONS.map((t) => (
                    <SelectItem key={t} value={t} className="text-xs">
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <Label className="text-2xs text-muted-foreground">Hasta</Label>
              <Select value={toTime} onValueChange={setToTime}>
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue placeholder="Hasta" />
                </SelectTrigger>
                <SelectContent className="max-h-48">
                  {TIME_OPTIONS.map((t) => (
                    <SelectItem key={t} value={t} className="text-xs">
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-1">
            <Label className="text-2xs text-muted-foreground">Modalidad</Label>
            <Select value={modality} onValueChange={(v) => setModality(v as ExchangeModality)}>
              <SelectTrigger className="h-8 text-xs">
                <SelectValue placeholder="Modalidad" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="BOTH" className="text-xs">Ambas (Virtual y Presencial)</SelectItem>
                <SelectItem value="VIRTUAL" className="text-xs">Solo Virtual</SelectItem>
                <SelectItem value="PRESENCIAL" className="text-xs">Solo Presencial</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <Button
            type="button"
            size="sm"
            variant="secondary"
            onClick={handleAddSlot}
            className="w-full h-8 text-xs font-semibold gap-1.5"
          >
            <Plus className="size-3.5" />
            Agregar a {DAYS[activeDayIndex].name}
          </Button>
        </div>

        {/* Acciones Rápidas (Presets) */}
        <div className="space-y-1.5 pt-1">
          <Label className="text-2xs font-bold uppercase tracking-wider text-muted-foreground">
            Acciones Rápidas
          </Label>
          <div className="flex flex-wrap gap-1.5">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleApplyWorkday}
              className="h-7 text-2xs gap-1"
            >
              <Zap className="size-3 text-amber-500" />
              Jornada Laboral (09:00 - 18:00)
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleCopyToWeekdays}
              className="h-7 text-2xs gap-1"
            >
              <Copy className="size-3 text-primary" />
              Copiar a Lun-Vie
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleClearDay}
              className="h-7 text-2xs text-destructive hover:bg-destructive/10"
            >
              Limpiar Día
            </Button>
          </div>
        </div>

        {/* Botón Principal de Guardado */}
        <div className="pt-2 border-t border-border">
          <Button
            type="button"
            onClick={handleSaveAll}
            disabled={isSavingAvailability}
            className="w-full h-9 text-xs font-bold gap-2"
          >
            <Save className="size-4" />
            {isSavingAvailability ? "Guardando en Servidor..." : "Guardar Disponibilidad Semanal"}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

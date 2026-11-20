import { useEffect, useState } from "react"
import {
  CalendarCheck,
  CalendarOff,
  Check,
  Pencil,
  Plus,
  Save,
  X,
} from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { useProfileStore } from "@/stores/profile-store"
import type { AvailabilitySlotInput, ExchangeModality } from "@/types/profile"

const DAYS = [
  { index: 0, name: "Lunes", short: "Lun", letter: "L" },
  { index: 1, name: "Martes", short: "Mar", letter: "M" },
  { index: 2, name: "Miércoles", short: "Mié", letter: "M" },
  { index: 3, name: "Jueves", short: "Jue", letter: "J" },
  { index: 4, name: "Viernes", short: "Vie", letter: "V" },
  { index: 5, name: "Sábado", short: "Sáb", letter: "S" },
  { index: 6, name: "Domingo", short: "Dom", letter: "D" },
]

const HALF_HOUR_TIMES = [
  "07:00",
  "07:30",
  "08:00",
  "08:30",
  "09:00",
  "09:30",
  "10:00",
  "10:30",
  "11:00",
  "11:30",
  "12:00",
  "12:30",
  "13:00",
  "13:30",
  "14:00",
  "14:30",
  "15:00",
  "15:30",
  "16:00",
  "16:30",
  "17:00",
  "17:30",
  "18:00",
  "18:30",
  "19:00",
  "19:30",
  "20:00",
  "20:30",
  "21:00",
  "21:30",
  "22:00",
]

interface BlockedHoliday {
  id: string
  label: string
}

export function AvailabilityPage() {
  const {
    profile,
    availabilitySlots,
    isSavingAvailability,
    loadProfile,
    loadAvailability,
    saveAvailability,
    removeAvailabilitySlot,
    patchProfile,
  } = useProfileStore()

  // Estado para Card_Editor_Nueva_Franja (n8187 en OpenPencil)
  const [selectedBuilderDays, setSelectedBuilderDays] = useState<number[]>([
    0, 1, 2, 3, 4,
  ])
  const [fromTime, setFromTime] = useState<string>("09:00")
  const [toTime, setToTime] = useState<string>("13:00")
  const [virtualChecked, setVirtualChecked] = useState<boolean>(true)
  const [presencialChecked, setPresencialChecked] = useState<boolean>(true)

  // Estado editable de la matriz semanal (n8220 Card_Dias_Configurados)
  const [draftSlots, setDraftSlots] = useState<
    Array<AvailabilitySlotInput & { id?: string }>
  >([])
  const [dayActiveMap, setDayActiveMap] = useState<Record<number, boolean>>({
    0: true,
    1: true,
    2: true,
    3: true,
    4: true,
    5: false,
    6: false,
  })

  // Parámetros de Políticas de Reserva (n8315 Card_Politicas_Reserva)
  const [sessionDuration, setSessionDuration] = useState<string>("30_60")
  const [bufferMinutes, setBufferMinutes] = useState<string>("15")
  const [minNotice, setMinNotice] = useState<string>("2h")
  const [maxWindow, setMaxWindow] = useState<string>("14d")

  // Columna derecha (n8328: GCalCard y BlockCard)
  const [gcalSynced, setGcalSynced] = useState<boolean>(true)
  const [holidays, setHolidays] = useState<BlockedHoliday[]>([
    { id: "h1", label: "25 Dic 2026 (Feriado Navidad) · Todo el día" },
    { id: "h2", label: "15 Jul - 20 Jul (Exámenes Facultad)" },
  ])

  useEffect(() => {
    void loadProfile()
    void loadAvailability()
  }, [loadProfile, loadAvailability])

  useEffect(() => {
    if (profile) {
      setBufferMinutes(String(profile.buffer_minutes ?? 15))
      setGcalSynced(Boolean(profile.gcal_synced ?? true))
    }
  }, [profile])

  useEffect(() => {
    if (availabilitySlots.length > 0) {
      setDraftSlots(
        availabilitySlots.map((s) => ({
          id: s.id,
          day_of_week: s.day_of_week,
          start_time: s.start_time,
          end_time: s.end_time,
          is_enabled: s.is_enabled,
          modality: s.modality || "BOTH",
        }))
      )
      const nextMap: Record<number, boolean> = {
        0: false,
        1: false,
        2: false,
        3: false,
        4: false,
        5: false,
        6: false,
      }
      for (const s of availabilitySlots) {
        if (s.is_enabled) nextMap[s.day_of_week] = true
      }
      setDayActiveMap(nextMap)
    }
  }, [availabilitySlots])

  const toggleBuilderDay = (dayIdx: number) => {
    setSelectedBuilderDays((prev) =>
      prev.includes(dayIdx)
        ? prev.filter((d) => d !== dayIdx)
        : [...prev, dayIdx].sort()
    )
  }

  const resolveBuilderModality = (): ExchangeModality => {
    if (virtualChecked && presencialChecked) return "BOTH"
    if (presencialChecked) return "PRESENCIAL"
    return "VIRTUAL"
  }

  const handleAddToSchedule = () => {
    if (toTime <= fromTime) {
      toast.error(
        "La hora 'Hasta' debe ser posterior a la hora 'Desde' (ej. 09:00 a 13:00)."
      )
      return
    }
    if (selectedBuilderDays.length === 0) {
      toast.error("Seleccioná al menos un día de la semana.")
      return
    }
    const mod = resolveBuilderModality()
    const nextDayMap = { ...dayActiveMap }
    let nextDraft = [...draftSlots]

    for (const dayIdx of selectedBuilderDays) {
      nextDayMap[dayIdx] = true
      // Evitar solapamiento en el mismo día reemplazando si se superpone
      nextDraft = nextDraft.filter(
        (s) =>
          !(
            s.day_of_week === dayIdx &&
            !(toTime <= s.start_time || fromTime >= s.end_time)
          )
      )
      nextDraft.push({
        day_of_week: dayIdx,
        start_time: fromTime,
        end_time: toTime,
        is_enabled: true,
        modality: mod,
      })
    }

    nextDraft.sort(
      (a, b) =>
        a.day_of_week - b.day_of_week ||
        a.start_time.localeCompare(b.start_time)
    )
    setDayActiveMap(nextDayMap)
    setDraftSlots(nextDraft)
    toast.success(
      "Franja agregada a la vista previa. Guardá los cambios para confirmar."
    )
  }

  const handleToggleDayRow = (dayIdx: number, enabled: boolean) => {
    setDayActiveMap((prev) => ({ ...prev, [dayIdx]: enabled }))
    if (enabled) {
      const hasSlots = draftSlots.some((s) => s.day_of_week === dayIdx)
      if (!hasSlots) {
        setDraftSlots((prev) => [
          ...prev,
          {
            day_of_week: dayIdx,
            start_time: "09:00",
            end_time: "13:00",
            is_enabled: true,
            modality: "BOTH",
          },
        ])
      }
    }
  }

  const handleQuickAddIntervalForDay = (dayIdx: number) => {
    setDayActiveMap((prev) => ({ ...prev, [dayIdx]: true }))
    setSelectedBuilderDays([dayIdx])
    toast.info(
      `Día ${DAYS[dayIdx]?.name} seleccionado arriba. Elegí el rango 'Desde / Hasta' y presioná '+ Agregar a la Agenda'.`
    )
  }

  const handleDeleteSlotPill = async (
    slot: AvailabilitySlotInput & { id?: string },
    idx: number
  ) => {
    if (slot.id) {
      await removeAvailabilitySlot(slot.id)
    } else {
      setDraftSlots((prev) => prev.filter((_, i) => i !== idx))
    }
  }

  const handleSaveAll = async () => {
    const activePayloadSlots: AvailabilitySlotInput[] = draftSlots
      .filter((s) => dayActiveMap[s.day_of_week] && s.is_enabled)
      .map((s) => ({
        day_of_week: s.day_of_week,
        start_time: s.start_time,
        end_time: s.end_time,
        is_enabled: true,
        modality: s.modality,
      }))

    await saveAvailability({
      slots: activePayloadSlots,
      timezone: profile?.timezone || "America/La_Paz",
      buffer_minutes: Number(bufferMinutes),
    })
  }

  const handleToggleGcal = async (checked: boolean) => {
    setGcalSynced(checked)
    await patchProfile({ gcal_synced: checked })
  }

  const handleAddHolidayBlock = () => {
    const newId = `h-${Date.now()}`
    setHolidays((prev) => [
      ...prev,
      { id: newId, label: "Próximo Feriado / Bloqueo Personal · Todo el día" },
    ])
    toast.success("Rango de fechas bloqueado agregado a tu agenda.")
  }

  const formatModalityLabel = (mod: ExchangeModality) => {
    if (mod === "BOTH") return "Virtual + Presencial"
    if (mod === "PRESENCIAL") return "Solo Presencial"
    return "Solo Virtual"
  }

  return (
    <div className="mx-auto w-full max-w-[1380px] p-4 md:p-6">
      {/* LAYOUT DE 2 COLUMNAS DENTRO DEL SHELL (Columna_Central_Editor + Columna_Derecha_Widgets de Vista 21 OpenPencil) */}
      <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-12">
        {/* COLUMNA CENTRAL EDITOR (n8175 - 810px en Web) */}
        <div className="space-y-5 xl:col-span-8">
          {/* 1. EdHead (n8176) */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h1 className="text-base font-bold tracking-tight text-foreground uppercase md:text-lg">
                GESTIÓN Y EDICIÓN DE DISPONIBILIDAD HORARIA
              </h1>
              <p className="mt-0.5 max-w-xl text-xs text-muted-foreground">
                Configurá tus franjas laborales, agregá o eliminá intervalos de
                30 minutos y sincronizá con tu calendario personal.
              </p>
            </div>

            <div className="flex shrink-0 items-center gap-2">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={handleAddToSchedule}
                className="h-9 gap-1.5 text-xs"
              >
                <Plus className="size-3.5" />
                Agregar Franja
              </Button>
              <Button
                type="button"
                size="sm"
                disabled={isSavingAvailability}
                onClick={() => void handleSaveAll()}
                className="h-9 gap-1.5 text-xs"
              >
                <Save className="size-3.5" />
                {isSavingAvailability ? "Guardando..." : "Guardar Cambios"}
              </Button>
            </div>
          </div>

          {/* 2. Card_Editor_Nueva_Franja (n8187 en Web / n8350 AddCardM en Mobile — Fondo #E6F4F2 / bg-primary/10) */}
          <Card className="border-primary/25 bg-primary/10 shadow-none">
            <CardContent className="space-y-3.5 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs font-bold tracking-wide text-primary uppercase">
                  NUEVA FRANJA HORARIA DISPONIBLE
                </span>
                <span className="text-[11px] font-medium text-primary">
                  Seleccioná días y rango de horas
                </span>
              </div>

              {/* DaysRow (Días: Lun Mar Mié Jue Vie Sáb Dom) */}
              <div className="flex flex-wrap items-center gap-2">
                <span className="mr-1 text-xs font-semibold text-foreground">
                  Días:
                </span>
                {DAYS.map((d) => {
                  const selected = selectedBuilderDays.includes(d.index)
                  return (
                    <Button
                      key={d.index}
                      type="button"
                      size="sm"
                      variant={selected ? "default" : "outline"}
                      onClick={() => toggleBuilderDay(d.index)}
                      className={`h-7 px-2.5 text-xs font-semibold ${
                        selected
                          ? "bg-primary text-primary-foreground"
                          : "bg-background text-muted-foreground"
                      }`}
                    >
                      <span className="hidden sm:inline">{d.short}</span>
                      <span className="sm:hidden">{d.letter}</span>
                    </Button>
                  )
                })}
              </div>

              {/* TimeInputsRow (Desde: 09:00 hs ▾ | Hasta: 13:00 hs ▾ | ☑ Virtual | ☑ Presencial | + Agregar a la Agenda) */}
              <div className="flex flex-col gap-3 pt-1 xl:flex-row xl:items-center xl:justify-between">
                <div className="flex flex-wrap items-center gap-3">
                  <div className="flex shrink-0 items-center gap-2">
                    <Label className="text-xs font-semibold">Desde:</Label>
                    <Select value={fromTime} onValueChange={setFromTime}>
                      <SelectTrigger className="h-8 w-[108px] bg-background text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {HALF_HOUR_TIMES.map((t) => (
                          <SelectItem key={`from-${t}`} value={t}>
                            {t} hs
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="flex shrink-0 items-center gap-2">
                    <Label className="text-xs font-semibold">Hasta:</Label>
                    <Select value={toTime} onValueChange={setToTime}>
                      <SelectTrigger className="h-8 w-[108px] bg-background text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {HALF_HOUR_TIMES.map((t) => (
                          <SelectItem key={`to-${t}`} value={t}>
                            {t} hs
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <label className="flex cursor-pointer items-center gap-1.5 text-xs font-medium text-primary">
                    <Checkbox
                      checked={virtualChecked}
                      onCheckedChange={(v) => setVirtualChecked(Boolean(v))}
                    />
                    <span>Virtual (WebRTC)</span>
                  </label>

                  <label className="flex cursor-pointer items-center gap-1.5 text-xs font-medium text-blue-800 dark:text-blue-300">
                    <Checkbox
                      checked={presencialChecked}
                      onCheckedChange={(v) => setPresencialChecked(Boolean(v))}
                    />
                    <span>Presencial (Punto Seguro)</span>
                  </label>

                  <Button
                    type="button"
                    size="sm"
                    onClick={handleAddToSchedule}
                    className="h-8 px-3 text-xs font-semibold"
                  >
                    + Agregar a la Agenda
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 3. Card_Dias_Configurados (n8220 HORARIOS SEMANALES ACTIVOS (FRANJAS EDITABLES):) */}
          <Card className="border-border/80 shadow-2xs">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-bold tracking-wide text-foreground uppercase">
                HORARIOS SEMANALES ACTIVOS (FRANJAS EDITABLES):
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2.5">
              {DAYS.map((d) => {
                const isDayEnabled = dayActiveMap[d.index] ?? false
                const daySlots = draftSlots
                  .map((s, idx) => ({ ...s, _idx: idx }))
                  .filter((s) => s.day_of_week === d.index && s.is_enabled)

                return (
                  <div
                    key={d.index}
                    className={`flex flex-col gap-2.5 rounded-xl border p-3 sm:flex-row sm:items-center sm:justify-between ${
                      isDayEnabled ? "bg-muted/25" : "bg-muted/60 opacity-80"
                    }`}
                  >
                    {/* Toggle + Nombre del Día */}
                    <div className="flex shrink-0 items-center justify-between sm:w-36">
                      <div className="flex items-center gap-2.5">
                        <Switch
                          checked={isDayEnabled}
                          onCheckedChange={(checked) =>
                            handleToggleDayRow(d.index, checked)
                          }
                        />
                        <span
                          className={`text-xs font-semibold ${
                            isDayEnabled
                              ? "text-foreground"
                              : "text-muted-foreground"
                          }`}
                        >
                          {d.name}
                        </span>
                      </div>
                      <span className="text-[11px] font-medium text-primary sm:hidden">
                        {isDayEnabled ? "● Activado" : "Descanso"}
                      </span>
                    </div>

                    {/* Contenedor de SlotPills o Leyenda de Descanso */}
                    <div className="flex flex-1 flex-wrap items-center gap-2">
                      {!isDayEnabled || daySlots.length === 0 ? (
                        <span className="text-xs text-muted-foreground italic">
                          No laborable (Día de descanso)
                        </span>
                      ) : (
                        daySlots.map((slot) => (
                          <div
                            key={`${slot.day_of_week}-${slot.start_time}-${slot.end_time}`}
                            className="inline-flex items-center gap-2 rounded-lg border bg-background px-2.5 py-1 text-xs shadow-2xs"
                          >
                            <span className="font-semibold text-foreground">
                              {slot.start_time} - {slot.end_time}
                            </span>
                            <Badge
                              variant="secondary"
                              className={`px-1.5 py-0 text-[10px] ${
                                slot.modality === "BOTH" ||
                                slot.modality === "PRESENCIAL"
                                  ? "text-blue-700 dark:text-blue-300"
                                  : "text-primary"
                              }`}
                            >
                              {formatModalityLabel(slot.modality)}
                            </Badge>
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              className="size-5 text-muted-foreground hover:text-foreground"
                              onClick={() => {
                                setSelectedBuilderDays([slot.day_of_week])
                                setFromTime(slot.start_time)
                                setToTime(slot.end_time)
                              }}
                              aria-label="Editar franja"
                            >
                              <Pencil className="size-3" />
                            </Button>
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              className="size-5 text-destructive hover:text-destructive"
                              onClick={() =>
                                void handleDeleteSlotPill(slot, slot._idx)
                              }
                              aria-label="Eliminar franja"
                            >
                              <X className="size-3.5" />
                            </Button>
                          </div>
                        ))
                      )}
                    </div>

                    {/* Acción Derecha (+ Intervalo / Habilitar) */}
                    <div className="flex shrink-0 justify-end">
                      {isDayEnabled ? (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => handleQuickAddIntervalForDay(d.index)}
                          className="h-7 px-2 text-xs font-semibold text-primary"
                        >
                          + Intervalo
                        </Button>
                      ) : (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => handleToggleDayRow(d.index, true)}
                          className="h-7 px-2 text-xs font-semibold text-primary"
                        >
                          Habilitar
                        </Button>
                      )}
                    </div>
                  </div>
                )
              })}
            </CardContent>
          </Card>

          {/* 4. Card_Politicas_Reserva (n8315: DURACIÓN DE SESIÓN | BUFFER DE DESCANSO | ANTICIPACIÓN MÍNIMA | VENTANA MÁXIMA FUTURA) */}
          <Card className="border-border/80 shadow-2xs">
            <CardContent className="grid grid-cols-1 gap-4 p-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="space-y-1">
                <Label className="text-[10px] font-bold tracking-wider text-muted-foreground uppercase">
                  DURACIÓN DE SESIÓN
                </Label>
                <Select
                  value={sessionDuration}
                  onValueChange={setSessionDuration}
                >
                  <SelectTrigger className="h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="30_60">30 o 60 minutos</SelectItem>
                    <SelectItem value="30">Solo 30 minutos</SelectItem>
                    <SelectItem value="60">Solo 60 minutos</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1">
                <Label className="text-[10px] font-bold tracking-wider text-muted-foreground uppercase">
                  BUFFER DE DESCANSO
                </Label>
                <Select value={bufferMinutes} onValueChange={setBufferMinutes}>
                  <SelectTrigger className="h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="0">Sin descanso (0 min)</SelectItem>
                    <SelectItem value="10">10 minutos entre clases</SelectItem>
                    <SelectItem value="15">15 minutos entre clases</SelectItem>
                    <SelectItem value="30">30 minutos entre clases</SelectItem>
                    <SelectItem value="60">60 minutos entre clases</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1">
                <Label className="text-[10px] font-bold tracking-wider text-muted-foreground uppercase">
                  ANTICIPACIÓN MÍNIMA
                </Label>
                <Select value={minNotice} onValueChange={setMinNotice}>
                  <SelectTrigger className="h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="2h">2 horas de aviso previo</SelectItem>
                    <SelectItem value="6h">6 horas de aviso previo</SelectItem>
                    <SelectItem value="24h">
                      24 horas de aviso previo
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1">
                <Label className="text-[10px] font-bold tracking-wider text-muted-foreground uppercase">
                  VENTANA MÁXIMA FUTURA
                </Label>
                <Select value={maxWindow} onValueChange={setMaxWindow}>
                  <SelectTrigger className="h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="7d">7 días hacia adelante</SelectItem>
                    <SelectItem value="14d">14 días hacia adelante</SelectItem>
                    <SelectItem value="30d">30 días hacia adelante</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* COLUMNA DERECHA WIDGETS (n8328 - 340px en Web: GCalCard + BlockCard) */}
        <div className="space-y-5 xl:col-span-4">
          {/* 1. GCalCard (n8329: SINCRONIZACIÓN DE CALENDARIO) */}
          <Card className="border-border/80 shadow-2xs">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between gap-2">
                <CardTitle className="flex items-center gap-1.5 text-xs font-bold tracking-wide text-primary uppercase">
                  <CalendarCheck className="size-4" />
                  SINCRONIZACIÓN DE CALENDARIO
                </CardTitle>
                <Switch
                  checked={gcalSynced}
                  onCheckedChange={(checked) => void handleToggleGcal(checked)}
                />
              </div>
            </CardHeader>
            <CardContent className="space-y-3 text-xs">
              <p className="leading-relaxed text-muted-foreground">
                Google Calendar sincronizado con{" "}
                <span className="font-medium text-foreground">
                  {profile?.gcal_calendar_email ||
                    profile?.email ||
                    "lucia.mendez@dev.uy"}
                </span>
                . Los eventos personales bloquean automáticamente los slots en
                SkillMatch para evitar superposiciones.
              </p>
              <div className="flex items-center gap-1.5 font-semibold text-emerald-600 dark:text-emerald-400">
                <Check className="size-3.5" />
                <span>
                  {gcalSynced
                    ? "Estado: Conexión en tiempo real ✓"
                    : "Estado: Sincronización en pausa"}
                </span>
              </div>
            </CardContent>
          </Card>

          {/* 2. BlockCard (n8333: BLOQUEOS Y FERIADOS) */}
          <Card className="border-border/80 shadow-2xs">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-1.5 text-xs font-bold tracking-wide text-foreground uppercase">
                <CalendarOff className="size-4 text-primary" />
                BLOQUEOS Y FERIADOS
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-2">
                {holidays.map((item) => (
                  <div
                    key={item.id}
                    className="flex items-center justify-between gap-2 rounded-lg bg-muted/50 px-2.5 py-1.5 text-xs text-muted-foreground"
                  >
                    <span className="truncate">• {item.label}</span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="size-5 shrink-0 text-destructive hover:text-destructive"
                      onClick={() =>
                        setHolidays((prev) =>
                          prev.filter((h) => h.id !== item.id)
                        )
                      }
                      aria-label="Quitar bloqueo"
                    >
                      <X className="size-3" />
                    </Button>
                  </div>
                ))}
              </div>

              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={handleAddHolidayBlock}
                className="h-8 w-full text-xs font-medium"
              >
                + Bloquear Rango de Fechas
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

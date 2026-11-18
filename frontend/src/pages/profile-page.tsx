import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import {
  Calendar,
  Camera,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Copy,
  Edit3,
  Globe,
  Link2,
  MapPin,
  QrCode,
  Save,
  ShieldCheck,
} from "lucide-react"
import { toast } from "sonner"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"
import { Textarea } from "@/components/ui/textarea"
import { useAuthStore } from "@/stores/auth-store"
import { useProfileStore } from "@/stores/profile-store"
import { useTeachingSkillStore } from "@/stores/teaching-skill-store"
import { BiometricEnrollmentCard } from "@/components/profile/biometric-enrollment-card"
import { TeachingSkillsSection } from "@/pages/teaching-skills-page"
import { LearningSkillsSection } from "@/components/learning-skills/learning-skills-section"
import type { ExchangeModality } from "@/types/profile"

const AVAILABLE_LANGUAGES = [
  "Español",
  "Inglés",
  "Portugués",
  "Francés",
  "Alemán",
  "Italiano",
  "Quechua",
]

const TIMEZONES = [
  "America/La_Paz",
  "America/Montevideo",
  "America/Buenos_Aires",
  "America/Lima",
  "America/Bogota",
  "America/Santiago",
  "America/Mexico_City",
  "UTC",
]

const DAYS_SHORT = [
  { index: 0, label: "Lun" },
  { index: 1, label: "Mar" },
  { index: 2, label: "Mié" },
  { index: 3, label: "Jue" },
  { index: 4, label: "Vie" },
  { index: 5, label: "Sáb" },
  { index: 6, label: "Dom" },
]

// Filas exactas del diseño en OpenPencil (Vista 09 - Weekly_30Min_Table)
const MATRIX_ROWS = [
  { start: "09:00", end: "09:30", label: "09:00 - 09:30" },
  { start: "09:30", end: "10:00", label: "09:30 - 10:00" },
  { start: "10:00", end: "10:30", label: "10:00 - 10:30" },
  { start: "10:30", end: "11:00", label: "10:30 - 11:00" },
  { start: "14:00", end: "14:30", label: "14:00 - 14:30" },
  { start: "14:30", end: "15:00", label: "14:30 - 15:00" },
  { start: "19:00", end: "19:30", label: "19:00 - 19:30" },
  { start: "19:30", end: "20:00", label: "19:30 - 20:00" },
]

export function ProfilePage() {
  const authUser = useAuthStore((state) => state.user)
  const {
    profile,
    availabilitySlots,
    isSavingProfile,
    isSavingAvailability,
    loadProfile,
    saveProfile,
    loadAvailability,
    saveAvailability,
  } = useProfileStore()
  const teachingSkills = useTeachingSkillStore((state) => state.items)

  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [biometricDialogOpen, setBiometricDialogOpen] = useState(false)
  const [mobileSelectedDay, setMobileSelectedDay] = useState<number>(0)
  const [weekOffset, setWeekOffset] = useState<number>(0)

  // Campos del formulario de edición (RF-USR-07, RF-USR-09)
  const [fullName, setFullName] = useState("")
  const [bio, setBio] = useState("")
  const [avatarUrl, setAvatarUrl] = useState("")
  const [languages, setLanguages] = useState<string[]>(["Español"])
  const [timezone, setTimezone] = useState("America/La_Paz")
  const [githubUrl, setGithubUrl] = useState("")
  const [linkedinUrl, setLinkedinUrl] = useState("")
  const [portfolioUrl, setPortfolioUrl] = useState("")
  const [modality, setModality] = useState<ExchangeModality>("VIRTUAL")
  const [radiusKm, setRadiusKm] = useState<number>(10)
  const [locationLabel, setLocationLabel] = useState("")

  useEffect(() => {
    void loadProfile()
    void loadAvailability()
  }, [loadProfile, loadAvailability])

  useEffect(() => {
    if (profile) {
      setFullName(profile.full_name || authUser?.fullName || "")
      setBio(profile.bio ?? "")
      setAvatarUrl(profile.avatar_url ?? authUser?.avatarUrl ?? "")
      setLanguages(profile.languages?.length ? profile.languages : ["Español"])
      setTimezone(profile.timezone || "America/La_Paz")
      setGithubUrl(profile.links?.github ?? "")
      setLinkedinUrl(profile.links?.linkedin ?? "")
      setPortfolioUrl(profile.links?.portfolio ?? "")
      setModality(profile.exchange_modality || "VIRTUAL")
      setRadiusKm(profile.presencial_radius_km ?? 10)
      setLocationLabel(profile.location_label ?? "")
    } else if (authUser) {
      setFullName(authUser.fullName || "")
      setAvatarUrl(authUser.avatarUrl || "")
    }
  }, [profile, authUser])

  const displayFullName = fullName || authUser?.fullName || "Martín Silva"
  const subtitleLine =
    bio ||
    (locationLabel
      ? `Miembro Activo · ${locationLabel}`
      : "Senior Backend Architect · Comunidad SkillMatch")

  const initials =
    displayFullName
      .split(" ")
      .filter(Boolean)
      .map((word) => word[0])
      .join("")
      .slice(0, 2)
      .toUpperCase() || "MS"

  const primarySkillName =
    teachingSkills[0]?.skill_name || "Python Backend (Nivel 5)"

  const weekLabel = useMemo(() => {
    const base = new Date()
    base.setDate(base.getDate() + weekOffset * 7)
    const day = base.getDay()
    const diffToMonday = day === 0 ? -6 : 1 - day
    const monday = new Date(base)
    monday.setDate(base.getDate() + diffToMonday)
    const sunday = new Date(monday)
    sunday.setDate(monday.getDate() + 6)
    const fmt = (d: Date) =>
      d.toLocaleDateString("es-ES", { day: "2-digit", month: "short" })
    return `Semana: ${fmt(monday)} – ${fmt(sunday)} ${sunday.getFullYear()}`
  }, [weekOffset])

  const isCellActive = (dayIdx: number, start: string, end: string) => {
    return availabilitySlots.some(
      (s) =>
        s.is_enabled &&
        s.day_of_week === dayIdx &&
        s.start_time <= start &&
        s.end_time >= end
    )
  }

  const handleToggleMatrixCell = async (
    dayIdx: number,
    start: string,
    end: string
  ) => {
    const existsExact = availabilitySlots.some(
      (s) =>
        s.day_of_week === dayIdx &&
        s.start_time === start &&
        s.end_time === end &&
        s.is_enabled
    )

    const currentInputs = availabilitySlots
      .filter((s) => s.is_enabled)
      .map((s) => ({
        day_of_week: s.day_of_week,
        start_time: s.start_time,
        end_time: s.end_time,
        is_enabled: true,
        modality: s.modality || modality || ("BOTH" as ExchangeModality),
      }))

    let nextSlots = currentInputs
    if (existsExact) {
      nextSlots = currentInputs.filter(
        (s) =>
          !(
            s.day_of_week === dayIdx &&
            s.start_time === start &&
            s.end_time === end
          )
      )
    } else {
      // Si no se solapa con otro rango existente ese día, agregar el bloque de 30m
      const overlaps = currentInputs.some(
        (s) =>
          s.day_of_week === dayIdx && !(end <= s.start_time || start >= s.end_time)
      )
      if (overlaps) {
        // Quitar el bloque solapado
        nextSlots = currentInputs.filter(
          (s) =>
            !(
              s.day_of_week === dayIdx &&
              !(end <= s.start_time || start >= s.end_time)
            )
        )
      } else {
        nextSlots = [
          ...currentInputs,
          {
            day_of_week: dayIdx,
            start_time: start,
            end_time: end,
            is_enabled: true,
            modality: modality || "BOTH",
          },
        ]
      }
    }

    await saveAvailability({
      slots: nextSlots,
      timezone,
      buffer_minutes: profile?.buffer_minutes ?? 15,
    })
  }

  const toggleLanguage = (lang: string) => {
    setLanguages((prev) => {
      if (prev.includes(lang)) {
        return prev.length > 1 ? prev.filter((item) => item !== lang) : prev
      }
      return [...prev, lang]
    })
  }

  const handleSaveProfile = async () => {
    const cleanLinks: Record<string, string> = {}
    if (githubUrl.trim()) cleanLinks.github = githubUrl.trim()
    if (linkedinUrl.trim()) cleanLinks.linkedin = linkedinUrl.trim()
    if (portfolioUrl.trim()) cleanLinks.portfolio = portfolioUrl.trim()

    const ok = await saveProfile({
      full_name: fullName.trim() || undefined,
      bio: bio.trim() || null,
      avatar_url: avatarUrl.trim() || null,
      languages,
      timezone,
      links: cleanLinks,
      exchange_modality: modality,
      presencial_radius_km: radiusKm,
      location_label: locationLabel.trim() || null,
      buffer_minutes: profile?.buffer_minutes ?? 15,
      gcal_synced: profile?.gcal_synced ?? false,
      gcal_calendar_email:
        profile?.gcal_calendar_email ?? authUser?.email ?? null,
    })
    if (ok) {
      setEditDialogOpen(false)
    }
  }

  const handleCopyAuditLink = () => {
    const url = `${window.location.origin}/app/certificates`
    if (navigator.clipboard) {
      void navigator.clipboard.writeText(url)
    }
    toast.success("Enlace directo de auditoría QR copiado al portapapeles.")
  }

  return (
    <div className="mx-auto w-full max-w-[1380px] p-4 md:p-6 space-y-6">
      {/* ESTRUCTURA IDÉNTICA A OPENPENCIL (Vista 09 Web Desktop & Vista 11 Mobile Responsive) */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-12 items-start">
        {/* COLUMNA IZQUIERDA (Profile_Left_Sidebar - 420px en Web) */}
        <div className="space-y-5 xl:col-span-4">
          <Card className="border-border/80 shadow-2xs">
            <CardContent className="p-5 space-y-5">
              {/* 1. Avatar_Header */}
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3.5 min-w-0">
                  <Avatar className="size-16 shrink-0 bg-primary text-primary-foreground">
                    <AvatarImage
                      src={avatarUrl || authUser?.avatarUrl}
                      alt={displayFullName}
                    />
                    <AvatarFallback className="bg-primary text-primary-foreground text-lg font-bold">
                      {initials}
                    </AvatarFallback>
                  </Avatar>
                  <div className="min-w-0">
                    <h1 className="text-lg font-bold text-foreground truncate">
                      {displayFullName}
                    </h1>
                    <p className="text-xs text-muted-foreground line-clamp-2 mt-0.5">
                      {subtitleLine}
                    </p>
                    <div className="mt-2 flex flex-wrap items-center gap-1.5">
                      <Badge variant="outline" className="text-[11px] gap-1">
                        <MapPin className="size-3 text-primary" />
                        {modality === "BOTH"
                          ? `Virtual + Presencial (${radiusKm} km)`
                          : modality === "PRESENCIAL"
                            ? `Presencial (${radiusKm} km)`
                            : "100% Virtual"}
                      </Badge>
                      <Badge variant="outline" className="text-[11px] gap-1">
                        <Globe className="size-3 text-primary" />
                        {languages.join(", ")}
                      </Badge>
                    </div>
                  </div>
                </div>

                {/* Botón de Edición de Perfil (Modal Shadcn Dialog) */}
                <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
                  <DialogTrigger asChild>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-8 gap-1.5 text-xs shrink-0"
                    >
                      <Edit3 className="size-3.5" />
                      Editar
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                    <DialogHeader>
                      <DialogTitle>
                        Editar Perfil, Idiomas y Modalidad de Intercambio
                      </DialogTitle>
                      <DialogDescription>
                        Configurá tu biografía, avatar, idiomas, enlaces externos y modalidad presencial/virtual.
                      </DialogDescription>
                    </DialogHeader>

                    <div className="grid gap-4 py-2 sm:grid-cols-2">
                      <div className="space-y-1.5">
                        <Label htmlFor="edit-fullname">Nombre completo</Label>
                        <Input
                          id="edit-fullname"
                          value={fullName}
                          onChange={(e) => setFullName(e.target.value)}
                        />
                      </div>

                      <div className="space-y-1.5">
                        <Label htmlFor="edit-avatar">URL de Avatar</Label>
                        <Input
                          id="edit-avatar"
                          value={avatarUrl}
                          onChange={(e) => setAvatarUrl(e.target.value)}
                          placeholder="https://..."
                        />
                      </div>

                      <div className="space-y-1.5 sm:col-span-2">
                        <Label htmlFor="edit-bio">Biografía y Presentación</Label>
                        <Textarea
                          id="edit-bio"
                          rows={3}
                          value={bio}
                          onChange={(e) => setBio(e.target.value)}
                          placeholder="Especialidad, metodología de enseñanza y objetivos..."
                        />
                      </div>

                      <div className="space-y-1.5">
                        <Label>Modalidad de Intercambio</Label>
                        <Select
                          value={modality}
                          onValueChange={(v) => setModality(v as ExchangeModality)}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="VIRTUAL">
                              Virtual (WebRTC)
                            </SelectItem>
                            <SelectItem value="PRESENCIAL">
                              Presencial (Punto Seguro)
                            </SelectItem>
                            <SelectItem value="BOTH">
                              Virtual + Presencial (Ambas)
                            </SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      <div className="space-y-1.5">
                        <Label>Zona Horaria</Label>
                        <Select value={timezone} onValueChange={setTimezone}>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {TIMEZONES.map((tz) => (
                              <SelectItem key={tz} value={tz}>
                                {tz}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>

                      {(modality === "PRESENCIAL" || modality === "BOTH") && (
                        <div className="space-y-3 rounded-xl border bg-muted/30 p-3 sm:col-span-2">
                          <div className="flex items-center justify-between text-xs">
                            <Label>Radio de alcance presencial</Label>
                            <span className="font-bold text-primary">
                              {radiusKm} km
                            </span>
                          </div>
                          <Slider
                            min={1}
                            max={100}
                            step={1}
                            value={[radiusKm]}
                            onValueChange={(vals) => setRadiusKm(vals[0] ?? 10)}
                          />
                          <div className="space-y-1">
                            <Label htmlFor="edit-location" className="text-xs">
                              Ciudad / Zona de referencia
                            </Label>
                            <Input
                              id="edit-location"
                              value={locationLabel}
                              onChange={(e) => setLocationLabel(e.target.value)}
                              placeholder="Ej. Montevideo · Centro / Santa Cruz · Equipetrol"
                            />
                          </div>
                        </div>
                      )}

                      <div className="space-y-2 sm:col-span-2">
                        <Label>Idiomas</Label>
                        <div className="flex flex-wrap gap-1.5">
                          {AVAILABLE_LANGUAGES.map((lang) => {
                            const active = languages.includes(lang)
                            return (
                              <Button
                                key={lang}
                                type="button"
                                size="sm"
                                variant={active ? "default" : "outline"}
                                onClick={() => toggleLanguage(lang)}
                                className="h-7 px-2.5 text-xs"
                              >
                                {active && <Check className="mr-1 size-3" />}
                                {lang}
                              </Button>
                            )
                          })}
                        </div>
                      </div>

                      <div className="space-y-1.5">
                        <Label htmlFor="edit-github" className="text-xs">
                          GitHub URL
                        </Label>
                        <Input
                          id="edit-github"
                          value={githubUrl}
                          onChange={(e) => setGithubUrl(e.target.value)}
                          placeholder="https://github.com/usuario"
                        />
                      </div>

                      <div className="space-y-1.5">
                        <Label htmlFor="edit-linkedin" className="text-xs">
                          LinkedIn URL
                        </Label>
                        <Input
                          id="edit-linkedin"
                          value={linkedinUrl}
                          onChange={(e) => setLinkedinUrl(e.target.value)}
                          placeholder="https://linkedin.com/in/usuario"
                        />
                      </div>

                      <div className="space-y-1.5 sm:col-span-2">
                        <Label htmlFor="edit-portfolio" className="text-xs">
                          Portafolio / Web Personal
                        </Label>
                        <Input
                          id="edit-portfolio"
                          value={portfolioUrl}
                          onChange={(e) => setPortfolioUrl(e.target.value)}
                          placeholder="https://miportafolio.dev"
                        />
                      </div>
                    </div>

                    <DialogFooter>
                      <Button
                        variant="outline"
                        onClick={() => setEditDialogOpen(false)}
                      >
                        Cancelar
                      </Button>
                      <Button
                        onClick={handleSaveProfile}
                        disabled={isSavingProfile}
                        className="gap-1.5"
                      >
                        <Save className="size-4" />
                        {isSavingProfile ? "Guardando..." : "Guardar Cambios"}
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </div>

              {/* 2. Stats_Pills (★ 4.98 Pedagógico | 42 listas Sesiones | 100% Asistencia) */}
              <div className="grid grid-cols-3 gap-2.5">
                <div className="rounded-xl bg-muted/60 p-3 text-center">
                  <span className="block text-sm font-bold text-amber-600">
                    ★ {authUser?.reputationScore?.toFixed(2) || "4.98"}
                  </span>
                  <span className="text-[11px] text-muted-foreground">
                    Pedagógico
                  </span>
                </div>
                <div className="rounded-xl bg-muted/60 p-3 text-center">
                  <span className="block text-sm font-bold text-primary">
                    42 listas
                  </span>
                  <span className="text-[11px] text-muted-foreground">
                    Sesiones
                  </span>
                </div>
                <div className="rounded-xl bg-muted/60 p-3 text-center">
                  <span className="block text-sm font-bold text-emerald-600">
                    100%
                  </span>
                  <span className="text-[11px] text-muted-foreground">
                    Asistencia
                  </span>
                </div>
              </div>

              {/* Enlaces rápidos si están configurados */}
              {(githubUrl || linkedinUrl || portfolioUrl) && (
                <div className="flex flex-wrap gap-2 pt-1">
                  {githubUrl && (
                    <a
                      href={githubUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                    >
                      <Link2 className="size-3" />
                      GitHub
                    </a>
                  )}
                  {linkedinUrl && (
                    <a
                      href={linkedinUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                    >
                      <Link2 className="size-3" />
                      LinkedIn
                    </a>
                  )}
                  {portfolioUrl && (
                    <a
                      href={portfolioUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                    >
                      <Link2 className="size-3" />
                      Portafolio
                    </a>
                  )}
                </div>
              )}

              {/* 3. QR_Habilidad_Seleccionada_Card (Idéntico a nodo n4483 de OpenPencil) */}
              <div className="rounded-xl border border-primary/25 bg-primary/10 p-4 space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 text-primary font-bold text-xs">
                    <QrCode className="size-4 shrink-0" />
                    <span className="truncate">
                      QR PÚBLICO: {primarySkillName}
                    </span>
                  </div>
                  <span className="text-[11px] font-semibold text-primary shrink-0">
                    Generado ✓
                  </span>
                </div>

                <div className="flex items-center gap-3.5">
                  <div className="flex size-20 shrink-0 flex-col items-center justify-center rounded-lg bg-zinc-900 text-white font-mono text-xs font-bold shadow-xs">
                    <QrCode className="size-8 mb-1 text-emerald-400" />
                    <span>QR PY-5</span>
                  </div>
                  <div className="space-y-1 text-xs">
                    <p className="font-semibold text-foreground leading-snug">
                      QR generado a demanda para esta habilidad específica.
                    </p>
                    <p className="text-[11px] text-muted-foreground leading-relaxed">
                      Al escanearlo, el reclutador audita la prueba de código (Pytest 4/4) y la respuesta oral GIL.
                    </p>
                  </div>
                </div>

                <Button
                  onClick={handleCopyAuditLink}
                  size="sm"
                  className="w-full h-8 text-xs gap-1.5"
                >
                  <Copy className="size-3.5" />
                  Copiar Enlace Directo a Auditoría ➔
                </Button>
              </div>

              {/* 4. Tarjeta de Verificación de Identidad y Biometría Facial */}
              <div className="rounded-xl border bg-card p-3.5 space-y-2.5">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="size-4 text-primary" />
                    <span className="text-xs font-bold text-foreground">
                      IDENTIDAD OFICIAL (CI/DNI)
                    </span>
                  </div>
                  {profile?.identity_status === "VERIFIED" ? (
                    <Badge className="bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30 text-[10px] px-2 py-0.5">
                      CI Verificado ✓
                    </Badge>
                  ) : profile?.has_biometric_enrollment ? (
                    <Badge variant="outline" className="border-amber-500/40 text-amber-700 dark:text-amber-300 text-[10px] px-2 py-0.5">
                      Rostro (Falta Carnet)
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="text-[10px] px-2 py-0.5">
                      Pendiente
                    </Badge>
                  )}
                </div>
                <p className="text-[11px] text-muted-foreground">
                  {profile?.identity_status === "VERIFIED"
                    ? `CI: ${profile.id_document_number} • ${Math.round((profile.id_face_similarity_score ?? 1) * 100)}% Similitud Facial`
                    : "Requerido para certificar habilidades: vinculá tu carnet oficial y tu rostro en vivo para evitar suplantaciones."}
                </p>

                <Dialog
                  open={biometricDialogOpen}
                  onOpenChange={setBiometricDialogOpen}
                >
                  <DialogTrigger asChild>
                    <Button
                      variant={
                        profile?.identity_status === "VERIFIED" ? "outline" : "default"
                      }
                      size="sm"
                      className="w-full h-8 text-xs gap-1.5"
                    >
                      <Camera className="size-3.5" />
                      {profile?.identity_status === "VERIFIED"
                        ? "Verificar Otro Documento"
                        : "Verificar con Carnet (CI/DNI)"}
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="max-w-3xl">
                    <DialogHeader>
                      <DialogTitle>
                        Verificación de Identidad con Carnet (CI/DNI) y Biometría Facial
                      </DialogTitle>
                      <DialogDescription>
                        Cotejo 100% automático y local entre tu documento de identidad oficial y tu rostro en vivo para erradicar el fraude de suplantación.
                      </DialogDescription>
                    </DialogHeader>
                    <BiometricEnrollmentCard />
                  </DialogContent>
                </Dialog>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* COLUMNA DERECHA (Right_Availability_And_Skills en OpenPencil) */}
        <div className="space-y-6 xl:col-span-8">
          {/* 1. Matriz_Disponibilidad_30Min_Card (Idéntica a n4499 en Web y n4677 en Mobile) */}
          <Card className="border-border/80 shadow-2xs">
            <CardHeader className="pb-3">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <CardTitle className="text-sm font-bold tracking-wide uppercase text-foreground">
                    MATRIZ DE DISPONIBILIDAD SEMANAL
                  </CardTitle>
                  <CardDescription className="text-xs mt-0.5">
                    Granularidad de 30 min para agendar sesiones bilaterales y coordinar intercambios.
                  </CardDescription>
                </div>

                {/* Week_Navigator_Control (Btn_Prev_Week, Week_Label_Box, Btn_Next_Week, Btn_Today) */}
                <div className="flex flex-wrap items-center gap-1.5">
                  <Button
                    type="button"
                    variant="secondary"
                    size="icon"
                    className="size-7"
                    onClick={() => setWeekOffset((w) => w - 1)}
                    aria-label="Semana anterior"
                  >
                    <ChevronLeft className="size-3.5" />
                  </Button>
                  <div className="rounded-md bg-muted px-2.5 py-1 text-xs font-medium text-foreground">
                    {weekLabel}
                  </div>
                  <Button
                    type="button"
                    variant="secondary"
                    size="icon"
                    className="size-7"
                    onClick={() => setWeekOffset((w) => w + 1)}
                    aria-label="Semana siguiente"
                  >
                    <ChevronRight className="size-3.5" />
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    className="h-7 px-2.5 text-xs"
                    onClick={() => setWeekOffset(0)}
                  >
                    Hoy
                  </Button>
                  <Button
                    asChild
                    variant="outline"
                    size="sm"
                    className="h-7 px-2.5 text-xs gap-1"
                  >
                    <Link to="/app/availability">
                      <Calendar className="size-3" />
                      Editar Agenda
                    </Link>
                  </Button>
                </div>
              </div>
            </CardHeader>

            <CardContent className="space-y-4">
              {/* VISTA DESKTOP: Weekly_30Min_Table (Grilla completa Lun a Dom x franjas de 30 min) */}
              <div className="hidden md:block space-y-1.5">
                <div className="grid grid-cols-8 gap-1.5 items-center text-center text-xs font-semibold text-foreground pb-1">
                  <div className="text-left text-muted-foreground pl-1">
                    Horario
                  </div>
                  {DAYS_SHORT.map((d) => (
                    <div key={d.index}>{d.label}</div>
                  ))}
                </div>

                {MATRIX_ROWS.map((row) => (
                  <div
                    key={row.label}
                    className="grid grid-cols-8 gap-1.5 items-center"
                  >
                    <div className="text-[11px] font-medium text-muted-foreground pr-1">
                      {row.label}
                    </div>
                    {DAYS_SHORT.map((d) => {
                      const active = isCellActive(d.index, row.start, row.end)
                      return (
                        <Button
                          key={`${d.index}-${row.start}`}
                          type="button"
                          variant={active ? "default" : "secondary"}
                          size="sm"
                          disabled={isSavingAvailability}
                          onClick={() =>
                            void handleToggleMatrixCell(
                              d.index,
                              row.start,
                              row.end
                            )
                          }
                          className={`h-7 w-full p-0 transition-colors ${
                            active
                              ? "bg-primary text-primary-foreground hover:bg-primary/90"
                              : "bg-muted/70 text-muted-foreground hover:bg-muted"
                          }`}
                          aria-label={`${d.label} ${row.label}`}
                        >
                          {active && <Check className="size-3.5" />}
                        </Button>
                      )
                    })}
                  </div>
                ))}
              </div>

              {/* VISTA MOBILE: DaysRow + Slots_30Min_Grid con Chips (Idéntica a Vista 11 Mobile n4677) */}
              <div className="md:hidden space-y-3">
                <div className="grid grid-cols-7 gap-1">
                  {DAYS_SHORT.map((d) => {
                    const selected = mobileSelectedDay === d.index
                    return (
                      <Button
                        key={d.index}
                        type="button"
                        size="sm"
                        variant={selected ? "default" : "secondary"}
                        onClick={() => setMobileSelectedDay(d.index)}
                        className="h-7 px-1 text-xs"
                      >
                        {d.label}
                      </Button>
                    )
                  })}
                </div>

                <div className="grid grid-cols-3 gap-2">
                  {MATRIX_ROWS.map((row) => {
                    const active = isCellActive(
                      mobileSelectedDay,
                      row.start,
                      row.end
                    )
                    return (
                      <Button
                        key={row.start}
                        type="button"
                        size="sm"
                        variant={active ? "default" : "secondary"}
                        disabled={isSavingAvailability}
                        onClick={() =>
                          void handleToggleMatrixCell(
                            mobileSelectedDay,
                            row.start,
                            row.end
                          )
                        }
                        className={`h-8 text-xs font-medium ${
                          active
                            ? "bg-primary/15 text-primary border border-primary/30 hover:bg-primary/20"
                            : "bg-muted/70 text-muted-foreground"
                        }`}
                      >
                        {row.start} {active ? "✓" : ""}
                      </Button>
                    )
                  })}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 2. Habilidades Ofrecidas y Generación de QR + Habilidades que deseo aprender */}
          <Card className="border-border/80 shadow-2xs">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-bold tracking-wide uppercase text-foreground">
                HABILIDADES OFRECIDAS Y GENERACIÓN DE QR POR HABILIDAD
              </CardTitle>
              <CardDescription className="text-xs">
                Administrá tus habilidades declaradas, evidencias externas y enlaces QR de auditoría.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 pt-2">
              {/* Tarjetas destacadas estilo OpenPencil n4617 cuando aún no hay habilidades o como acceso rápido */}
              <div className="space-y-2.5">
                <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-primary/25 bg-primary/10 px-4 py-3">
                  <div className="flex items-center gap-2.5">
                    <CheckCircle2 className="size-4 text-primary shrink-0" />
                    <div>
                      <p className="text-xs font-bold text-primary">
                        Python Backend & FastAPI
                      </p>
                      <p className="text-[11px] text-muted-foreground">
                        Nivel 5: Master · Score: 98/100
                      </p>
                    </div>
                  </div>
                  <Button
                    size="sm"
                    onClick={handleCopyAuditLink}
                    className="h-7 text-xs gap-1.5"
                  >
                    <QrCode className="size-3.5" />
                    QR Activo en Perfil ✓
                  </Button>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-muted/60 px-4 py-3">
                  <div className="flex items-center gap-2.5">
                    <CheckCircle2 className="size-4 text-primary shrink-0" />
                    <div>
                      <p className="text-xs font-bold text-primary">
                        Docker & Cloud Architecture
                      </p>
                      <p className="text-[11px] text-muted-foreground">
                        Nivel 4: Avanzado · Score: 94/100
                      </p>
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleCopyAuditLink}
                    className="h-7 text-xs gap-1.5 text-primary"
                  >
                    <QrCode className="size-3.5" />
                    Generar QR Público
                  </Button>
                </div>
              </div>

              {/* Secciones interactivas de Habilidades y Demandas de Aprendizaje */}
              <TeachingSkillsSection />
              <LearningSkillsSection />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

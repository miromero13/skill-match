import { useState } from "react"
import {
  ShieldCheck,
  Star,
  MapPin,
  Globe,
  Coins,
  ArrowLeftRight,
  User,
  Sparkles,
  CheckCircle2,
} from "lucide-react"
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import type { TutorSearchResult, TutorTeachingSkill } from "@/types/search"

interface TutorCardProps {
  tutor: TutorSearchResult
  onProposeSwap?: (tutor: TutorSearchResult) => void
}

const LEVEL_LABELS: Record<string, string> = {
  BEGINNER: "Principiante",
  INTERMEDIATE: "Intermedio",
  ADVANCED: "Avanzado",
  EXPERT: "Experto",
}

export function TutorCard({ tutor, onProposeSwap }: TutorCardProps) {
  const [profileDialogOpen, setProfileDialogOpen] = useState(false)

  const initials = tutor.full_name
    .split(" ")
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase()

  const minPointsRate = tutor.skills
    .filter((s) => s.accepts_points && s.hourly_points_rate !== null)
    .reduce<number | null>(
      (min, s) => (min === null || (s.hourly_points_rate ?? 0) < min ? s.hourly_points_rate! : min),
      null
    )

  return (
    <>
      <Card className="flex flex-col justify-between overflow-hidden border border-border/80 bg-card transition-all duration-200 hover:shadow-md hover:border-primary/40">
        <CardHeader className="space-y-3 p-4 sm:p-5 pb-3">
          {/* Header con Avatar, Nombre, Rating y Sello IA */}
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-3">
              <Avatar className="h-12 w-12 border-2 border-primary/20 shrink-0">
                <AvatarImage src={tutor.avatar_url || undefined} alt={tutor.full_name} />
                <AvatarFallback className="bg-primary/10 text-primary font-bold text-sm">
                  {initials || "SM"}
                </AvatarFallback>
              </Avatar>

              <div className="min-w-0">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <h3 className="font-semibold text-base leading-tight truncate text-foreground">
                    {tutor.full_name}
                  </h3>
                  {tutor.has_verified_skills && (
                    <span
                      title="Instructor verificado con pruebas de IA"
                      className="inline-flex items-center text-emerald-600 dark:text-emerald-400"
                    >
                      <ShieldCheck className="h-4 w-4 shrink-0 fill-emerald-100 dark:fill-emerald-950" />
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground flex-wrap">
                  {tutor.location_label && (
                    <span className="flex items-center gap-0.5">
                      <MapPin className="h-3 w-3 shrink-0" />
                      <span className="truncate max-w-[130px]">{tutor.location_label}</span>
                    </span>
                  )}
                  {tutor.distance_km !== null && tutor.distance_km !== undefined && (
                    <Badge variant="secondary" className="px-1.5 py-0 text-[10px] font-medium bg-muted">
                      {tutor.distance_km} km
                    </Badge>
                  )}
                </div>
              </div>
            </div>

            {/* Rating pill */}
            <div className="flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-xs font-semibold text-amber-700 dark:text-amber-400 shrink-0">
              <Star className="h-3.5 w-3.5 fill-amber-500 text-amber-500" />
              <span>{tutor.rating.toFixed(1)}</span>
              {tutor.total_reviews > 0 && (
                <span className="text-[10px] font-normal text-muted-foreground">({tutor.total_reviews})</span>
              )}
            </div>
          </div>

          {/* Modalidad de enseñanza */}
          <div className="flex items-center gap-1.5 flex-wrap">
            {tutor.exchange_modality === "VIRTUAL" && (
              <Badge variant="outline" className="text-[11px] gap-1 font-normal border-blue-200 text-blue-700 dark:border-blue-900 dark:text-blue-400">
                <Globe className="h-3 w-3" /> Clases Virtuales
              </Badge>
            )}
            {tutor.exchange_modality === "PRESENCIAL" && (
              <Badge variant="outline" className="text-[11px] gap-1 font-normal border-amber-200 text-amber-700 dark:border-amber-900 dark:text-amber-400">
                <MapPin className="h-3 w-3" /> Presencial ({tutor.presencial_radius_km} km)
              </Badge>
            )}
            {tutor.exchange_modality === "BOTH" && (
              <Badge variant="outline" className="text-[11px] gap-1 font-normal border-emerald-200 text-emerald-700 dark:border-emerald-900 dark:text-emerald-400">
                <Sparkles className="h-3 w-3" /> Presencial y Virtual
              </Badge>
            )}
          </div>

          {/* Bio breve */}
          {tutor.bio && (
            <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
              {tutor.bio}
            </p>
          )}
        </CardHeader>

        <CardContent className="px-4 sm:px-5 py-2 space-y-2">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Habilidades que enseña:
          </span>
          <div className="flex flex-col gap-1.5">
            {tutor.skills.map((skill: TutorTeachingSkill) => (
              <div
                key={skill.id}
                className="flex items-center justify-between rounded-lg bg-muted/50 p-2 text-xs border border-border/40 gap-2"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="font-medium text-foreground truncate">{skill.skill_name}</span>
                    {skill.is_verified && (
                      <Badge className="bg-emerald-600 hover:bg-emerald-700 text-white text-[9px] px-1.5 py-0 h-4 gap-0.5">
                        <CheckCircle2 className="h-2.5 w-2.5" /> IA
                      </Badge>
                    )}
                  </div>
                  <span className="text-[10px] text-muted-foreground">
                    {skill.category_name} • {skill.years_of_experience} {skill.years_of_experience === 1 ? "año" : "años"} exp.
                  </span>
                </div>

                <Badge variant="outline" className="text-[10px] shrink-0 font-normal">
                  {LEVEL_LABELS[skill.declared_level] || skill.declared_level}
                </Badge>
              </div>
            ))}
          </div>
        </CardContent>

        <CardFooter className="flex items-center justify-between gap-2 p-4 sm:p-5 pt-3 border-t bg-muted/20">
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            {minPointsRate !== null ? (
              <span className="flex items-center gap-1 font-semibold text-emerald-700 dark:text-emerald-400">
                <Coins className="h-3.5 w-3.5" />
                <span>{minPointsRate} pts/hr</span>
              </span>
            ) : (
              <span className="flex items-center gap-1 text-[11px] font-medium text-muted-foreground">
                <ArrowLeftRight className="h-3 w-3 text-primary" />
                <span>Intercambio directo</span>
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              className="h-8 text-xs px-2.5"
              onClick={() => setProfileDialogOpen(true)}
            >
              <User className="h-3.5 w-3.5 mr-1" />
              Perfil
            </Button>
            <Button
              size="sm"
              className="h-8 text-xs px-3 gap-1 bg-primary text-primary-foreground hover:bg-primary/90"
              onClick={() => onProposeSwap?.(tutor)}
            >
              <ArrowLeftRight className="h-3.5 w-3.5" />
              <span>Intercambio</span>
            </Button>
          </div>
        </CardFooter>
      </Card>

      {/* Modal de perfil expandido */}
      <Dialog open={profileDialogOpen} onOpenChange={setProfileDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <div className="flex items-center gap-3">
              <Avatar className="h-12 w-12 border">
                <AvatarImage src={tutor.avatar_url || undefined} alt={tutor.full_name} />
                <AvatarFallback className="bg-primary/10 text-primary font-bold">
                  {initials}
                </AvatarFallback>
              </Avatar>
              <div>
                <DialogTitle className="text-lg flex items-center gap-1.5">
                  {tutor.full_name}
                  {tutor.has_verified_skills && (
                    <ShieldCheck className="h-4 w-4 text-emerald-600" />
                  )}
                </DialogTitle>
                <DialogDescription className="text-xs">
                  {tutor.location_label || "Ubicación no especificada"} • {tutor.rating} ★
                </DialogDescription>
              </div>
            </div>
          </DialogHeader>

          <div className="space-y-4 py-2 text-xs">
            {tutor.bio && (
              <div>
                <span className="font-semibold text-foreground block mb-1">Presentación:</span>
                <p className="text-muted-foreground leading-relaxed">{tutor.bio}</p>
              </div>
            )}

            <div>
              <span className="font-semibold text-foreground block mb-2">Habilidades en oferta:</span>
              <div className="space-y-2">
                {tutor.skills.map((s) => (
                  <div key={s.id} className="p-2.5 rounded-lg border bg-muted/30 flex justify-between items-center">
                    <div>
                      <span className="font-bold text-foreground block">{s.skill_name}</span>
                      <span className="text-[11px] text-muted-foreground">{s.description || `${s.years_of_experience} años de experiencia`}</span>
                    </div>
                    <div className="text-right">
                      <Badge variant="secondary" className="text-[10px]">
                        {LEVEL_LABELS[s.declared_level] || s.declared_level}
                      </Badge>
                      {s.accepts_points && s.hourly_points_rate && (
                        <span className="text-[10px] text-emerald-600 block mt-0.5 font-medium">
                          {s.hourly_points_rate} pts/hr
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

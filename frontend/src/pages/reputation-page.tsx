import { useEffect } from "react"
import { useParams, Link } from "react-router-dom"
import { useReputationStore } from "@/stores/reputation-store"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Separator } from "@/components/ui/separator"
import {
  Star,
  ShieldCheck,
  ClockCheck,
  Award,
  Sparkles,
  Calendar,
  MessageSquare,
  Loader2,
  ChevronLeft,
} from "lucide-react"

import { useAuthStore } from "@/stores/auth-store"

export function ReputationPage() {
  const { userId: paramUserId } = useParams<{ userId: string }>()
  const currentUser = useAuthStore((s) => s.user)
  const targetUserId = paramUserId || currentUser?.id
  const { currentReputation, isLoadingReputation, loadUserReputation } = useReputationStore()

  useEffect(() => {
    if (targetUserId) {
      loadUserReputation(targetUserId)
    }
  }, [targetUserId, loadUserReputation])

  if (isLoadingReputation) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3">
        <Loader2 className="h-8 w-8 animate-spin text-[#00786F]" />
        <p className="text-sm text-muted-foreground">Cargando perfil de reputación y confianza...</p>
      </div>
    )
  }

  if (!currentReputation) {
    return (
      <div className="container max-w-4xl py-12 text-center space-y-4">
        <h2 className="text-xl font-bold">No se encontró el perfil de reputación</h2>
        <p className="text-sm text-muted-foreground">
          El usuario solicitado no existe o no tiene actividad pública registrada.
        </p>
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-xs text-[#2DD4BF] hover:underline"
        >
          <ChevronLeft className="h-4 w-4" /> Volver al inicio
        </Link>
      </div>
    )
  }

  const {
    full_name,
    avatar_url,
    trust_score,
    overall_rating,
    total_reviews,
    ratings_breakdown,
    factors,
    badges,
    recent_reviews,
  } = currentReputation

  // Mapeo dinámico de iconos para insignias
  const getBadgeIcon = (iconName: string) => {
    switch (iconName) {
      case "ShieldCheck":
        return <ShieldCheck className="h-5 w-5 text-[#2DD4BF]" />
      case "Star":
        return <Star className="h-5 w-5 text-amber-400 fill-amber-400" />
      case "ClockCheck":
        return <ClockCheck className="h-5 w-5 text-emerald-400" />
      case "Award":
      default:
        return <Award className="h-5 w-5 text-indigo-400" />
    }
  }

  return (
    <div className="container max-w-5xl py-8 space-y-8 animate-in fade-in duration-300">
      {/* Botón Volver */}
      <div>
        <Link
          to="/app/sessions"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <ChevronLeft className="h-4 w-4" /> Volver a mis sesiones
        </Link>
      </div>

      {/* Hero Card: Perfil y Puntaje de Confianza */}
      <Card className="border-border bg-card text-card-foreground shadow-sm overflow-hidden">
        <CardContent className="p-6 sm:p-8">
          <div className="flex flex-col md:flex-row items-center md:items-start gap-6 justify-between">
            {/* Información del Usuario */}
            <div className="flex flex-col sm:flex-row items-center sm:items-start gap-4 text-center sm:text-left">
              <Avatar className="h-20 w-20 border-2 border-primary shadow-sm">
                <AvatarImage src={avatar_url || undefined} alt={full_name} />
                <AvatarFallback className="bg-primary/10 text-primary font-bold text-xl">
                  {full_name.slice(0, 2).toUpperCase()}
                </AvatarFallback>
              </Avatar>
              <div className="space-y-1">
                <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2">
                  <h1 className="text-2xl font-black tracking-tight text-foreground">{full_name}</h1>
                  <Badge className="bg-primary/10 text-primary border border-primary/20 text-[10px] font-bold uppercase tracking-wider">
                    Miembro Verificado
                  </Badge>
                </div>
                <div className="flex items-center justify-center sm:justify-start gap-2 pt-1">
                  <div className="flex items-center text-amber-500 dark:text-amber-400 font-extrabold text-base">
                    <Star className="h-4 w-4 fill-amber-500 dark:fill-amber-400 mr-1" />
                    <span>{overall_rating.toFixed(1)}</span>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    ({total_reviews} {total_reviews === 1 ? "reseña" : "reseñas de alumnos"})
                  </span>
                </div>
              </div>
            </div>

            {/* Puntaje de Confianza Dinámico (0-100%) */}
            <div className="w-full md:w-64 p-4 rounded-xl bg-muted/40 border border-border space-y-2.5">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-foreground flex items-center gap-1.5">
                  <Sparkles className="h-3.5 w-3.5 text-primary" /> Puntaje de Confianza
                </span>
                <span className="font-black text-sm text-primary">{trust_score}%</span>
              </div>
              <Progress value={trust_score} className="h-2.5 bg-muted" />
              <p className="text-[10px] text-muted-foreground leading-tight">
                Calculado con IA ({factors.ia_verified_score.toFixed(0)}%), feedback de pares (
                {factors.peer_feedback_score.toFixed(0)}%) y asistencia ({factors.attendance_score.toFixed(0)}%).
              </p>
            </div>
          </div>

          <Separator className="my-6 bg-border" />

          {/* Desglose de 3 Criterios Pedagógicos */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="p-3.5 rounded-lg bg-muted/40 border border-border space-y-1">
              <span className="text-[11px] text-muted-foreground font-medium">Puntualidad y Asistencia</span>
              <div className="flex items-center justify-between">
                <span className="text-lg font-bold text-foreground">{ratings_breakdown.punctuality.toFixed(1)}</span>
                <div className="flex text-amber-500 dark:text-amber-400">
                  <Star className="h-3.5 w-3.5 fill-amber-500 dark:fill-amber-400" />
                </div>
              </div>
            </div>

            <div className="p-3.5 rounded-lg bg-muted/40 border border-border space-y-1">
              <span className="text-[11px] text-muted-foreground font-medium">Claridad y Pedagogía</span>
              <div className="flex items-center justify-between">
                <span className="text-lg font-bold text-foreground">{ratings_breakdown.pedagogy.toFixed(1)}</span>
                <div className="flex text-amber-500 dark:text-amber-400">
                  <Star className="h-3.5 w-3.5 fill-amber-500 dark:fill-amber-400" />
                </div>
              </div>
            </div>

            <div className="p-3.5 rounded-lg bg-muted/40 border border-border space-y-1">
              <span className="text-[11px] text-muted-foreground font-medium">Dominio de la Habilidad</span>
              <div className="flex items-center justify-between">
                <span className="text-lg font-bold text-foreground">{ratings_breakdown.domain.toFixed(1)}</span>
                <div className="flex text-amber-500 dark:text-amber-400">
                  <Star className="h-3.5 w-3.5 fill-amber-500 dark:fill-amber-400" />
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Grid de Insignias Obtenidas */}
      <div className="space-y-4">
        <h2 className="text-lg font-bold text-foreground tracking-tight flex items-center gap-2">
          <Award className="h-5 w-5 text-primary" /> Insignias y Logros de Confianza
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {badges.map((badge) => (
            <Card
              key={badge.code}
              className={`border-border bg-card text-card-foreground transition-all ${
                badge.is_active ? "opacity-100 hover:border-primary/50 shadow-xs" : "opacity-40 grayscale"
              }`}
            >
              <CardContent className="p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="p-2 rounded-md bg-muted/50 border border-border">
                    {getBadgeIcon(badge.icon)}
                  </div>
                  {badge.is_active ? (
                    <Badge className="bg-primary/10 text-primary border border-primary/20 text-[9px] font-bold uppercase">
                      Activa
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="text-[9px] text-muted-foreground border-border">
                      Bloqueada
                    </Badge>
                  )}
                </div>
                <h3 className="font-bold text-sm text-foreground">{badge.title}</h3>
                <p className="text-[11px] text-muted-foreground leading-snug">{badge.description}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Muro de Reseñas y Testimonios */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-foreground tracking-tight flex items-center gap-2">
            <MessageSquare className="h-5 w-5 text-primary" /> Reseñas y Testimonios de la Comunidad
          </h2>
          <span className="text-xs text-muted-foreground">{total_reviews} en total</span>
        </div>

        {recent_reviews.length === 0 ? (
          <Card className="border-border bg-card p-8 text-center text-muted-foreground text-xs shadow-xs">
            Este usuario aún no tiene testimonios públicos registrados.
          </Card>
        ) : (
          <div className="space-y-3">
            {recent_reviews.map((review) => (
              <Card key={review.id} className="border-border bg-card text-card-foreground shadow-xs">
                <CardContent className="p-5 space-y-3">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-center gap-3">
                      <Avatar className="h-9 w-9 border border-border">
                        <AvatarImage src={review.reviewer_avatar || undefined} />
                        <AvatarFallback className="bg-muted text-xs font-bold text-foreground">
                          {review.reviewer_name.slice(0, 2).toUpperCase()}
                        </AvatarFallback>
                      </Avatar>
                      <div>
                        <h4 className="font-semibold text-xs text-foreground">{review.reviewer_name}</h4>
                        <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
                          <Calendar className="h-3 w-3" />
                          <span>{new Date(review.created_at).toLocaleDateString()}</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 font-bold text-xs text-amber-500 dark:text-amber-400 bg-muted/50 px-2.5 py-1 rounded-md border border-border">
                      <Star className="h-3 w-3 fill-amber-500 dark:fill-amber-400" />
                      <span>{review.overall_rating.toFixed(1)}</span>
                    </div>
                  </div>

                  {review.comment ? (
                    <p className="text-xs text-foreground leading-relaxed italic bg-muted/30 p-3 rounded-lg border border-border">
                      "{review.comment}"
                    </p>
                  ) : (
                    <p className="text-[11px] text-muted-foreground italic">Calificación numérica sin comentario escrito.</p>
                  )}

                  <div className="flex flex-wrap gap-4 text-[11px] text-muted-foreground pt-1">
                    <span>Puntualidad: <strong className="text-foreground">{review.rating_punctuality}★</strong></span>
                    <span>Pedagogía: <strong className="text-foreground">{review.rating_pedagogy}★</strong></span>
                    <span>Dominio: <strong className="text-foreground">{review.rating_domain}★</strong></span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

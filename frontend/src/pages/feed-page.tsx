import { useEffect } from "react"
import { Link } from "react-router-dom"
import { MatchSuggestions } from "@/components/matches/matches-suggestions"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  ShieldCheck,
  ArrowRight,
  Calendar,
  Star,
  Plus,
  BookOpen,
} from "lucide-react"
import { useTeachingSkillStore } from "@/stores/teaching-skill-store"
import { useLearningSkillStore } from "@/stores/learning-skill-store"

export function FeedPage() {
  const teachingSkills = useTeachingSkillStore((s) => s.items)
  const loadTeachingSkills = useTeachingSkillStore((s) => s.load)
  const isTeachingLoading = useTeachingSkillStore((s) => s.loading)

  const learningSkills = useLearningSkillStore((s) => s.learningSkills)
  const fetchLearningSkills = useLearningSkillStore((s) => s.fetchLearningSkills)
  const isLearningLoading = useLearningSkillStore((s) => s.isLoading)

  useEffect(() => {
    void loadTeachingSkills(1)
    void fetchLearningSkills()
  }, [loadTeachingSkills, fetchLearningSkills])

  const hasSkills = teachingSkills.length > 0 || learningSkills.length > 0
  const isLoading = isTeachingLoading || isLearningLoading

  return (
    <div className="flex-1 p-4 lg:p-6 bg-muted/20 min-h-screen">
      <div className="mx-auto max-w-6xl grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* CENTER COLUMN: Main Feed (8 cols) */}
        <div className="lg:col-span-8 space-y-6">
          <MatchSuggestions preview />
        </div>

        {/* RIGHT COLUMN: User Widgets & Next Session (4 cols) */}
        <div className="lg:col-span-4 space-y-5">
          {/* Card 1: Tus Habilidades */}
          <Card className="rounded-xl border shadow-xs bg-card">
            <CardContent className="p-4 space-y-3">
              <div className="flex items-center justify-between pb-1">
                <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                  TUS HABILIDADES
                </span>
                <Link to="/app/profile" className="text-xs font-bold text-primary hover:underline flex items-center gap-1">
                  <span>Gestionar</span>
                  <ArrowRight className="h-3 w-3" />
                </Link>
              </div>

              {isLoading ? (
                <p className="text-xs text-muted-foreground py-2 text-center">Cargando habilidades...</p>
              ) : !hasSkills ? (
                <div className="text-center py-4 px-2 space-y-3 border border-dashed rounded-lg bg-muted/30">
                  <BookOpen className="h-6 w-6 text-muted-foreground mx-auto" />
                  <div className="space-y-1">
                    <p className="text-xs font-semibold text-foreground">Aún no registraste habilidades</p>
                    <p className="text-[11px] text-muted-foreground leading-relaxed">
                      Agrega lo que puedes enseñar o lo que deseas aprender para recibir propuestas de intercambio.
                    </p>
                  </div>
                  <div className="flex flex-col gap-1.5 pt-1">
                    <Button size="sm" asChild variant="outline" className="w-full text-xs h-7">
                      <Link to="/app/teaching-skills">
                        <Plus className="h-3 w-3 mr-1" />
                        Habilidades que enseño
                      </Link>
                    </Button>
                    <Button size="sm" asChild variant="outline" className="w-full text-xs h-7">
                      <Link to="/app/learning-skills">
                        <Plus className="h-3 w-3 mr-1" />
                        Habilidades que busco
                      </Link>
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  {teachingSkills.slice(0, 2).map((item) => (
                    <div key={`teach-${item.id}`} className="rounded-lg border bg-primary/5 p-3 space-y-1">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5 font-bold text-xs text-foreground">
                          <span className="truncate">{item.skill_name}</span>
                          {item.status === "VERIFICADA" && (
                            <ShieldCheck className="h-3.5 w-3.5 text-primary shrink-0" />
                          )}
                        </div>
                        <Badge
                          variant={item.status === "VERIFICADA" ? "default" : "secondary"}
                          className="text-[10px] px-1.5 py-0 shrink-0"
                        >
                          {item.status === "VERIFICADA" ? "Verificada ✓" : "Declarada"}
                        </Badge>
                      </div>
                      <span className="text-[11px] text-muted-foreground block">
                        Enseñas · {item.years_of_experience} {item.years_of_experience === 1 ? "año" : "años"} exp.
                      </span>
                    </div>
                  ))}

                  {learningSkills.slice(0, 2).map((item) => (
                    <div key={`learn-${item.id}`} className="rounded-lg border bg-card p-3 space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-xs text-foreground truncate">
                          {item.skill?.name || "Habilidad"}
                        </span>
                        <Badge variant="outline" className="text-[10px] px-1.5 py-0 shrink-0">
                          Aprendes
                        </Badge>
                      </div>
                      <span className="text-[11px] text-muted-foreground block">
                        Deseas aprender · Urgencia {item.urgency || "Normal"}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Card 2: Próxima Sesión Agendada */}
          <Card className="rounded-xl border shadow-xs bg-card">
            <CardContent className="p-4 space-y-3">
              <div className="flex items-center gap-2 text-muted-foreground font-bold text-xs">
                <Calendar className="h-4 w-4" />
                <span>PRÓXIMA SESIÓN AGENDADA</span>
              </div>

              <div className="text-center py-4 px-2 space-y-2 border border-dashed rounded-lg bg-muted/30">
                <p className="text-xs text-muted-foreground">
                  No tienes sesiones programadas próximamente.
                </p>
                <Button size="sm" asChild variant="outline" className="text-xs h-7">
                  <Link to="/app/search">Buscar instructores</Link>
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Card 3: Índice de Confianza */}
          <Card className="rounded-xl border shadow-xs bg-card">
            <CardContent className="p-4 space-y-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground block">
                ÍNDICE DE CONFIANZA
              </span>

              <div className="flex items-center gap-1.5 font-bold text-sm text-foreground">
                <Star className="h-4 w-4 text-muted-foreground" />
                <span>Nuevo Miembro</span>
              </div>

              <p className="text-xs text-muted-foreground leading-relaxed">
                Completa tus primeros intercambios para construir tu historial y reputación comunitaria.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

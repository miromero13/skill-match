import { Link } from "react-router-dom"
import { MatchSuggestions } from "@/components/matches/matches-suggestions"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  ShieldCheck,
  ArrowRight,
  Calendar,
  Star,
} from "lucide-react"

export function FeedPage() {
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

              {/* Item 1 */}
              <div className="rounded-lg border bg-primary/5 p-3 space-y-1">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 font-bold text-xs text-foreground">
                    <span>Python Backend</span>
                    <ShieldCheck className="h-3.5 w-3.5 text-primary" />
                  </div>
                  <span className="text-[10px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded">
                    Certificado IA
                  </span>
                </div>
                <span className="text-[11px] text-muted-foreground block">
                  Enseñas · Nivel 5 (Master)
                </span>
              </div>

              {/* Item 2 */}
              <div className="rounded-lg border bg-card p-3 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-xs text-foreground">Bases de Datos SQL</span>
                  <span className="text-[10px] font-medium text-muted-foreground bg-muted px-2 py-0.5 rounded">
                    Declarado
                  </span>
                </div>
                <span className="text-[11px] text-muted-foreground block">
                  Enseñas · Nivel Intermedio
                </span>
              </div>

              {/* Item 3 */}
              <div className="rounded-lg border bg-card p-3 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-xs text-foreground">Guitarra Acústica</span>
                  <span className="text-[10px] font-medium text-muted-foreground bg-muted px-2 py-0.5 rounded">
                    Declarado
                  </span>
                </div>
                <span className="text-[11px] text-muted-foreground block">
                  Aprendes · Nivel Inicial
                </span>
              </div>
            </CardContent>
          </Card>

          {/* Card 2: Próxima Sesión Agendada */}
          <Card className="rounded-xl border border-primary/30 shadow-xs bg-primary/5">
            <CardContent className="p-4 space-y-3">
              <div className="flex items-center gap-2 text-primary font-bold text-xs">
                <Calendar className="h-4 w-4" />
                <span>PRÓXIMA SESIÓN AGENDADA</span>
              </div>

              <div className="space-y-1">
                <h4 className="font-bold text-sm text-foreground">
                  Hoy, 19:30 hrs (Virtual)
                </h4>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Enseñas Python a Mateo F. Sala abre 10 min antes.
                </p>
              </div>

              <Button size="sm" asChild className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-bold text-xs gap-1.5">
                <Link to="/app/exam-demo">
                  <span>Ingresar a la Sala</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </Button>
            </CardContent>
          </Card>

          {/* Card 3: Índice de Confianza */}
          <Card className="rounded-xl border shadow-xs bg-card">
            <CardContent className="p-4 space-y-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground block">
                ÍNDICE DE CONFIANZA
              </span>

              <div className="flex items-center gap-1.5 font-bold text-base text-foreground">
                <Star className="h-4 w-4 fill-primary text-primary" />
                <span>4.95 / 5.0 (14 Reseñas)</span>
              </div>

              <p className="text-xs text-muted-foreground leading-relaxed">
                100% puntualidad · 0 quejas · Pasaporte auditado.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

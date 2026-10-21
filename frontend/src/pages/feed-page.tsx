import { Link } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  ShieldCheck,
  ArrowLeftRight,
  Clock,
  Sparkles,
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
          {/* 1. Deep Teal Hero Banner */}
          <div className="rounded-2xl bg-primary p-6 text-primary-foreground shadow-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="space-y-1.5 max-w-md">
              <div className="flex items-center gap-2">
                <Sparkles className="h-5 w-5 shrink-0" />
                <h2 className="font-bold text-base sm:text-lg leading-tight">
                  ¡Tenés 3 nuevos matches para aprender Guitarra!
                </h2>
              </div>
              <p className="text-xs text-primary-foreground/80 leading-relaxed">
                Usuarios certificados por IA buscan aprender tus conocimientos en Python.
              </p>
            </div>
            <Button
              size="sm"
              asChild
              className="bg-background text-primary hover:bg-background/90 font-bold text-xs rounded-full px-4 shrink-0 shadow-xs"
            >
              <Link to="/app/search" className="flex items-center gap-1.5">
                <span>Explorar Matches</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </Button>
          </div>

          {/* 2. Match Card (Sofía Rossi) */}
          <Card className="rounded-2xl border shadow-xs bg-card overflow-hidden">
            <CardContent className="p-5 sm:p-6 space-y-5">
              {/* Header: User Info & Compatibility Badge */}
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-full bg-primary text-primary-foreground font-black text-sm shrink-0">
                    SR
                  </div>
                  <div>
                    <h3 className="font-bold text-base text-foreground leading-snug">
                      Sofía Rossi
                    </h3>
                    <p className="text-xs text-muted-foreground">
                      Guitarrista Clásica & Aprendiz de Programación · Buenos Aires
                    </p>
                  </div>
                </div>

                <div className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-bold text-primary shrink-0">
                  <Sparkles className="h-3.5 w-3.5" />
                  <span>98% Compatibilidad</span>
                </div>
              </div>

              {/* Reciprocal Swap Box */}
              <div className="rounded-xl border bg-muted/20 p-4">
                <div className="grid grid-cols-11 items-center gap-2">
                  {/* Left: She Teaches */}
                  <div className="col-span-5 space-y-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground block">
                      ELLA TE ENSEÑA
                    </span>
                    <div className="flex items-center gap-1 font-bold text-sm text-foreground">
                      <span>Guitarra Clásica & Solfeo</span>
                      <ShieldCheck className="h-4 w-4 text-primary shrink-0" />
                    </div>
                    <span className="text-xs font-semibold text-primary block">
                      Nivel 4 (Avanzado) · Verificado IA
                    </span>
                  </div>

                  {/* Center: Bidirectional Swap Icon */}
                  <div className="col-span-1 flex justify-center">
                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/10 text-primary">
                      <ArrowLeftRight className="h-4 w-4" />
                    </div>
                  </div>

                  {/* Right: You Teach */}
                  <div className="col-span-5 space-y-1 text-right">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground block">
                      VOS LE ENSEÑAS
                    </span>
                    <div className="flex items-center justify-end gap-1 font-bold text-sm text-foreground">
                      <span>Python Backend & FastAPI</span>
                      <ShieldCheck className="h-4 w-4 text-primary shrink-0" />
                    </div>
                    <span className="text-xs font-semibold text-primary block">
                      Nivel 5 (Master) · Verificado IA
                    </span>
                  </div>
                </div>
              </div>

              {/* Schedule Info */}
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Clock className="h-4 w-4 text-muted-foreground shrink-0" />
                <span>Coincidencia de horario: Martes y Jueves 18:30 a 20:00 (Modalidad Virtual)</span>
              </div>

              {/* Action Buttons */}
              <div className="flex flex-wrap items-center gap-3 pt-1">
                <Button className="bg-primary hover:bg-primary/90 text-primary-foreground text-xs font-bold gap-2 rounded-lg px-5 shadow-xs">
                  <ArrowLeftRight className="h-3.5 w-3.5" />
                  <span>Proponer Intercambio</span>
                </Button>
                <Button variant="outline" className="text-xs font-semibold gap-2 rounded-lg px-4 border-border">
                  <ShieldCheck className="h-3.5 w-3.5 text-primary" />
                  <span>Ver Pasaporte de Sofía</span>
                </Button>
              </div>
            </CardContent>
          </Card>
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

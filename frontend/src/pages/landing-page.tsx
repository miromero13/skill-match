import { Link } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { ArrowRight, Code2, Music, Activity, Check, Lock, ArrowLeftRight } from "lucide-react"

export function LandingPage() {
  return (
    <div className="flex flex-col bg-background text-foreground">
      {/* 1. HERO SECTION */}
      <section className="relative overflow-hidden border-b py-16 md:py-24">
        <div className="container mx-auto max-w-7xl px-4 sm:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
            {/* Left Column */}
            <div className="lg:col-span-7 space-y-6">
              <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-3.5 py-1 text-xs font-semibold text-primary">
                <span className="h-2 w-2 rounded-full bg-primary" />
                <span>PRIMERA RED DE SKILL SWAPPING CON VALIDACIÓN POR IA PROPIA</span>
              </div>

              <h1 className="text-4xl sm:text-5xl lg:text-[54px] font-extrabold tracking-tight text-foreground leading-[1.12]">
                Aprende lo que quieras <br />
                enseñando lo que sabes. <br />
                <span className="text-primary">Validado con IA.</span>
              </h1>

              <p className="text-sm sm:text-base text-muted-foreground max-w-xl leading-relaxed">
                Intercambiá conocimientos de forma justa y objetiva sin intermediarios costosos. Tu nivel técnico se certifica con desafíos en Docker, análisis acústico y visión motriz.
              </p>

              <div className="pt-2">
                <Button size="lg" asChild className="bg-primary hover:bg-primary/90 text-primary-foreground font-semibold px-6 py-6 text-sm shadow-sm rounded-lg">
                  <Link to="/app" className="flex items-center gap-2">
                    <span>Unirse a la Comunidad (3 Validaciones Gratis)</span>
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
                <p className="mt-3 text-xs text-muted-foreground flex items-center gap-1.5">
                  <Check className="h-3.5 w-3.5 text-primary shrink-0" />
                  <span>Registro instantáneo con Google, WhatsApp y GitHub · Sin contraseñas</span>
                </p>
              </div>
            </div>

            {/* Right Column: Floating Match Card Preview */}
            <div className="lg:col-span-5 flex justify-center">
              <Card className="w-full max-w-md shadow-md border-border/80 bg-card rounded-2xl overflow-hidden">
                <div className="p-5 space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-primary">
                      MATCH RECÍPROCO EN VIVO (ALTA AFINIDAD 96%)
                    </span>
                  </div>

                  <div className="rounded-xl border bg-muted/30 p-4 space-y-3">
                    <div className="grid grid-cols-11 items-center gap-2">
                      {/* Counterpart A */}
                      <div className="col-span-5 space-y-1">
                        <span className="font-bold text-xs text-foreground block">
                          Lucía Méndez · Nivel 4
                        </span>
                        <div className="flex items-center gap-1 text-[11px] text-primary font-medium">
                          <span>Enseña: Python FastAPI</span>
                          <Check className="h-3 w-3 stroke-[3]" />
                        </div>
                      </div>

                      {/* Reciprocal Icon */}
                      <div className="col-span-1 flex justify-center">
                        <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-primary">
                          <ArrowLeftRight className="h-3.5 w-3.5" />
                        </div>
                      </div>

                      {/* Counterpart B */}
                      <div className="col-span-5 space-y-1 text-right">
                        <span className="font-bold text-xs text-foreground block">
                          Sofía Rossi · Nivel 5
                        </span>
                        <div className="flex items-center justify-end gap-1 text-[11px] text-primary font-medium">
                          <span>Enseña: Figma Systems</span>
                          <Check className="h-3 w-3 stroke-[3]" />
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 text-[11px] text-muted-foreground pt-1">
                    <Lock className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    <span>Depósito seguro de 50 SP retenido en Escrow · Liberación al finalizar la clase</span>
                  </div>
                </div>
              </Card>
            </div>
          </div>
        </div>
      </section>

      {/* 2. ¿CÓMO FUNCIONA SKILLMATCH? */}
      <section id="como-funciona" className="py-20 container mx-auto max-w-7xl px-4 sm:px-8">
        <div className="text-center mb-14">
          <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight uppercase text-foreground">
            ¿CÓMO FUNCIONA SKILLMATCH?
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Step 1 */}
          <Card className="rounded-xl border shadow-xs bg-card">
            <CardContent className="p-6 space-y-2.5">
              <span className="text-[11px] font-extrabold uppercase tracking-wider text-primary">
                PASO 1
              </span>
              <h3 className="font-bold text-base text-foreground">
                Registrá tus Habilidades
              </h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Indicá qué podés enseñar y qué querés aprender. Configurá tu agenda de franjas horarias de 30 minutos.
              </p>
            </CardContent>
          </Card>

          {/* Step 2 */}
          <Card className="rounded-xl border shadow-xs bg-card">
            <CardContent className="p-6 space-y-2.5">
              <span className="text-[11px] font-extrabold uppercase tracking-wider text-primary">
                PASO 2
              </span>
              <h3 className="font-bold text-base text-foreground">
                Certificá tu Nivel con IA
              </h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Demostrá tu conocimiento con pruebas en Sandbox Docker, análisis espectral o visión motriz para obtener tu Sello Verificado.
              </p>
            </CardContent>
          </Card>

          {/* Step 3 */}
          <Card className="rounded-xl border shadow-xs bg-card">
            <CardContent className="p-6 space-y-2.5">
              <span className="text-[11px] font-extrabold uppercase tracking-wider text-primary">
                PASO 3
              </span>
              <h3 className="font-bold text-base text-foreground">
                Trueque Bilateral & Escrow
              </h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Conectá con personas compatibles, agendá la sesión (Virtual o Presencial) y asegurá la clase con garantía de Escrow.
              </p>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* 3. EVALUACIÓN OBJETIVA CON INTELIGENCIA ARTIFICIAL */}
      <section id="ia-demo" className="py-20 border-t bg-muted/20">
        <div className="container mx-auto max-w-7xl px-4 sm:px-8">
          <div className="text-center mb-14">
            <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight uppercase text-foreground">
              EVALUACIÓN OBJETIVA CON INTELIGENCIA ARTIFICIAL
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Area 1: Code */}
            <Card className="rounded-xl border shadow-xs bg-card">
              <CardContent className="p-6 space-y-3">
                <div className="flex items-center justify-between">
                  <Code2 className="h-6 w-6 text-primary" />
                  <span className="text-[10px] font-mono font-bold tracking-wider text-primary uppercase">
                    DOCKER SANDBOX
                  </span>
                </div>
                <h3 className="font-bold text-base text-foreground">
                  Programación & Backend
                </h3>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Evaluación en contenedores efímeros aislados, análisis estático de complejidad por AST y defensa oral.
                </p>
                <p className="text-xs font-semibold text-primary pt-2 border-t">
                  Prueba clave: CRUD asíncrono con 4/4 Pytest y Whisper
                </p>
              </CardContent>
            </Card>

            {/* Area 2: Music */}
            <Card className="rounded-xl border shadow-xs bg-card">
              <CardContent className="p-6 space-y-3">
                <div className="flex items-center justify-between">
                  <Music className="h-6 w-6 text-primary" />
                  <span className="text-[10px] font-mono font-bold tracking-wider text-primary uppercase">
                    ESPECTROGRAMA LIBROSA
                  </span>
                </div>
                <h3 className="font-bold text-base text-foreground">
                  Música & Instrumentos
                </h3>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Procesamiento de audio espectral en tiempo real para verificar afinación de cuerdas, tempo y armonía.
                </p>
                <p className="text-xs font-semibold text-primary pt-2 border-t">
                  Prueba clave: Detección de centésimas de semitono y BPM
                </p>
              </CardContent>
            </Card>

            {/* Area 3: Sports */}
            <Card className="rounded-xl border shadow-xs bg-card">
              <CardContent className="p-6 space-y-3">
                <div className="flex items-center justify-between">
                  <Activity className="h-6 w-6 text-primary" />
                  <span className="text-[10px] font-mono font-bold tracking-wider text-primary uppercase">
                    VISIÓN CON OPENCV
                  </span>
                </div>
                <h3 className="font-bold text-base text-foreground">
                  Deportes & Fútbol
                </h3>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Tracking de pose corporal y detección esférica de balón para contar repeticiones y control motriz.
                </p>
                <p className="text-xs font-semibold text-primary pt-2 border-t">
                  Prueba clave: Conteo automático de toques y estabilidad
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* 4. MÉTRICAS CONSOLIDADAS DE LA COMUNIDAD */}
      <section id="metricas" className="py-20 border-y bg-primary/5 dark:bg-primary/10">
        <div className="container mx-auto max-w-7xl px-4 sm:px-8 text-center space-y-12">
          <h2 className="text-xs sm:text-sm font-extrabold uppercase tracking-widest text-primary">
            MÉTRICAS CONSOLIDADAS DE LA COMUNIDAD
          </h2>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-8">
            <div className="space-y-1">
              <span className="text-3xl sm:text-4xl font-black text-primary tracking-tight block">
                4,850+
              </span>
              <span className="text-xs font-medium text-foreground block">
                Horas de Clase Realizadas
              </span>
            </div>

            <div className="space-y-1">
              <span className="text-3xl sm:text-4xl font-black text-primary tracking-tight block">
                98.4%
              </span>
              <span className="text-xs font-medium text-foreground block">
                Satisfacción en Reseñas
              </span>
            </div>

            <div className="space-y-1">
              <span className="text-3xl sm:text-4xl font-black text-primary tracking-tight block">
                1,240+
              </span>
              <span className="text-xs font-medium text-foreground block">
                Habilidades Certificadas con IA
              </span>
            </div>

            <div className="space-y-1">
              <span className="text-3xl sm:text-4xl font-black text-primary tracking-tight block">
                100%
              </span>
              <span className="text-xs font-medium text-foreground block">
                Fondos Protegidos por Escrow
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* 5. CALL TO ACTION FINAL */}
      <section className="py-24 container mx-auto max-w-4xl px-4 sm:px-8 text-center space-y-5">
        <h2 className="text-3xl sm:text-4xl font-extrabold text-foreground tracking-tight">
          Unite a la red de intercambio formativo más confiable
        </h2>
        <p className="text-xs sm:text-sm text-muted-foreground max-w-xl mx-auto leading-relaxed">
          Registrate gratis hoy y obtené tus 3 primeras validaciones técnicas supervisadas por IA sin costo.
        </p>
        <div className="pt-2">
          <Button size="lg" asChild className="bg-primary hover:bg-primary/90 text-primary-foreground font-semibold px-8 py-6 text-sm rounded-lg shadow-sm">
            <Link to="/app" className="flex items-center gap-2">
              <span>Crear Cuenta Gratuita en 1 Clic</span>
              <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        </div>
      </section>
    </div>
  )
}

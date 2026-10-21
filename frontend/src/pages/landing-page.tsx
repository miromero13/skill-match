import { Link } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import {
  ArrowRight,
  Code2,
  Music,
  Activity,
  Check,
  Lock,
  ArrowLeftRight,
  ShieldCheck,
  KeyRound,
  Scale,
  Globe,
} from "lucide-react"

export function LandingPage() {
  return (
    <div className="flex flex-col bg-background text-foreground">
      {/* 1. HERO SECTION (Node n9195 Mobile / n8986 Desktop) */}
      <section className="relative overflow-hidden border-b bg-[#F8FAFB] dark:bg-background min-h-[calc(100dvh-54px)] sm:min-h-[calc(100vh-64px)] flex flex-col justify-center py-6 sm:py-16">
        <div className="container mx-auto max-w-7xl px-4 sm:px-8 w-full">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
            {/* Left Column */}
            <div className="lg:col-span-7 flex flex-col items-center lg:items-start text-center lg:text-left space-y-3 sm:space-y-6">
              {/* Mobile Badge (Node n9196) */}
              <span className="sm:hidden text-[9px] font-extrabold tracking-wider text-[#00786F] dark:text-primary uppercase">
                ● TRUEQUE FORMATIVO CON IA
              </span>
              {/* Desktop Badge (Node n8987) */}
              <div className="hidden sm:inline-flex items-center gap-2 rounded-full bg-primary/10 px-3.5 py-1 text-xs font-semibold text-primary">
                <span className="h-2 w-2 rounded-full bg-primary" />
                <span>PRIMERA RED DE SKILL SWAPPING CON VALIDACIÓN POR IA PROPIA</span>
              </div>

              {/* Headline (Node n9197 Mobile / n8988 Desktop) */}
              <h1 className="text-2xl sm:text-5xl lg:text-[54px] font-black tracking-tight text-[#090B0C] dark:text-foreground leading-tight sm:leading-[1.12]">
                Aprende lo que quieras <br className="hidden sm:inline" />
                enseñando lo que sabes.
                <span className="hidden sm:inline">
                  <br />
                  <span className="text-[#00786F] dark:text-primary">Validado con IA.</span>
                </span>
              </h1>

              {/* Subtitle (Node n9198 Mobile / n8989 Desktop) */}
              <p className="text-[11px] sm:text-base text-[#67787C] dark:text-muted-foreground max-w-xl leading-relaxed">
                <span className="sm:hidden">
                  Intercambiá conocimientos de forma justa. Tu nivel técnico se valida con pruebas reales supervisadas por IA propia.
                </span>
                <span className="hidden sm:inline">
                  Intercambiá conocimientos de forma justa y objetiva sin intermediarios costosos. Tu nivel técnico se certifica con desafíos en Docker, análisis acústico y visión motriz.
                </span>
              </p>

              {/* CTA Button (Node n9199 Mobile / n8991 Desktop) */}
              <div className="pt-1 sm:pt-2 w-full sm:w-auto">
                <Button
                  size="lg"
                  asChild
                  className="w-full sm:w-auto bg-[#00786F] hover:bg-[#00786F]/90 text-[#F0FDFA] font-bold h-11 sm:h-12 px-6 text-[11px] sm:text-sm shadow-sm rounded-lg"
                >
                  <Link to="/app" className="flex items-center justify-center gap-2">
                    <span className="sm:hidden">Unirse Gratis (3 Certificaciones) ➔</span>
                    <span className="hidden sm:inline">Unirse a la Comunidad (3 Validaciones Gratis) ➔</span>
                  </Link>
                </Button>
                <p className="mt-3 text-xs text-[#67787C] dark:text-muted-foreground hidden sm:flex items-center gap-1.5">
                  <Check className="h-3.5 w-3.5 text-primary shrink-0" />
                  <span>Registro instantáneo con Google, WhatsApp y GitHub · Sin contraseñas</span>
                </p>
              </div>
            </div>

            {/* Right Column: Floating Match Card Preview (Desktop Only: Node n8994) */}
            <div className="hidden lg:flex lg:col-span-5 justify-center">
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

      {/* 2. ¿CÓMO FUNCIONA SKILLMATCH? (Node n9201 Mobile / n9008 Desktop) */}
      <section id="como-funciona" className="scroll-mt-14 sm:scroll-mt-16 min-h-dvh sm:min-h-screen flex flex-col justify-center py-8 sm:py-20 bg-white dark:bg-card">
        <div className="container mx-auto max-w-7xl px-4 sm:px-8 w-full">
          <div className="text-center mb-4 sm:mb-14">
            <h2 className="text-base sm:text-3xl font-black tracking-tight uppercase text-[#090B0C] dark:text-foreground">
              <span className="sm:hidden">¿CÓMO FUNCIONA?</span>
              <span className="hidden sm:inline">¿CÓMO FUNCIONA SKILLMATCH?</span>
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5 sm:gap-6">
            {/* Step 1 (Node n9203 Mobile / n9010 Desktop) */}
            <div
              className="rounded-lg sm:rounded-xl sm:border sm:shadow-xs bg-[#F8FAFB] dark:bg-muted/40 sm:bg-card p-3 sm:p-6 space-y-0.5 sm:space-y-2.5 transition-all"
            >
              <span className="hidden sm:block text-[11px] font-extrabold uppercase tracking-wider text-primary">
                PASO 1
              </span>
              <h3 className="font-bold text-[11px] sm:text-base text-[#090B0C] dark:text-foreground">
                <span className="sm:hidden">Paso 1: </span>Registrá tus habilidades
              </h3>
              <p className="text-[9px] sm:text-xs text-[#67787C] dark:text-muted-foreground leading-relaxed">
                <span className="sm:hidden">Lo que enseñás y lo que querés aprender.</span>
                <span className="hidden sm:inline">Indicá qué podés enseñar y qué querés aprender. Configurá tu agenda de franjas horarias de 30 minutos.</span>
              </p>
            </div>

            {/* Step 2 (Node n9206 Mobile / n9014 Desktop) */}
            <div className="rounded-lg sm:rounded-xl sm:border sm:shadow-xs bg-[#F8FAFB] dark:bg-muted/40 sm:bg-card p-3 sm:p-6 space-y-0.5 sm:space-y-2.5">
              <span className="hidden sm:block text-[11px] font-extrabold uppercase tracking-wider text-primary">
                PASO 2
              </span>
              <h3 className="font-bold text-[11px] sm:text-base text-[#090B0C] dark:text-foreground">
                <span className="sm:hidden">Paso 2: </span>Certificá tu nivel con IA
              </h3>
              <p className="text-[9px] sm:text-xs text-[#67787C] dark:text-muted-foreground leading-relaxed">
                <span className="sm:hidden">Pruebas en Docker, audio y visión motriz.</span>
                <span className="hidden sm:inline">Demostrá tu conocimiento con pruebas en Sandbox Docker, análisis espectral o visión motriz para obtener tu Sello Verificado.</span>
              </p>
            </div>

            {/* Step 3 (Node n9209 Mobile / n9018 Desktop) */}
            <div
              className="rounded-lg sm:rounded-xl sm:border sm:shadow-xs bg-[#F8FAFB] dark:bg-muted/40 sm:bg-card p-3 sm:p-6 space-y-0.5 sm:space-y-2.5 transition-all"
            >
              <span className="hidden sm:block text-[11px] font-extrabold uppercase tracking-wider text-primary">
                PASO 3
              </span>
              <h3 className="font-bold text-[11px] sm:text-base text-[#090B0C] dark:text-foreground">
                <span className="sm:hidden">Paso 3: </span>Hacé match y coordiná
              </h3>
              <p className="text-[9px] sm:text-xs text-[#67787C] dark:text-muted-foreground leading-relaxed">
                <span className="sm:hidden">Trueques seguros con depósito Escrow.</span>
                <span className="hidden sm:inline">Conectá con personas compatibles, agendá la sesión (Virtual o Presencial) y asegurá la clase con garantía de Escrow.</span>
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 3. EVALUACIÓN OBJETIVA CON INTELIGENCIA ARTIFICIAL (Node n9212 Mobile / n9024 Desktop) */}
      <section
        id="ia-demo"
        className="scroll-mt-14 sm:scroll-mt-16 min-h-dvh sm:min-h-screen flex flex-col justify-center py-8 sm:py-20 border-t bg-[#F8FAFB] dark:bg-muted/20"
      >
        <div className="container mx-auto max-w-7xl px-4 sm:px-8 w-full">
          <div className="text-center mb-4 sm:mb-14">
            <h2 className="text-base sm:text-3xl font-black tracking-tight uppercase text-[#090B0C] dark:text-foreground">
              <span className="sm:hidden">3 ÁREAS DE VALIDACIÓN POR IA</span>
              <span className="hidden sm:inline">EVALUACIÓN OBJETIVA CON INTELIGENCIA ARTIFICIAL</span>
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5 sm:gap-6">
            {/* Area 1: Code (Node n9214 Mobile / n9026 Desktop) */}
            <div className="rounded-lg sm:rounded-xl border border-[#E3E7E8] dark:border-border sm:shadow-xs bg-white dark:bg-card p-3 sm:p-6 space-y-0.5 sm:space-y-3">
              <div className="hidden sm:flex items-center justify-between">
                <Code2 className="h-6 w-6 text-primary" />
                <span className="text-[10px] font-mono font-bold tracking-wider text-primary uppercase">
                  DOCKER SANDBOX
                </span>
              </div>
              <h3 className="font-extrabold text-[11px] sm:text-base text-[#090B0C] dark:text-foreground">
                Programación & Backend
              </h3>
              <p className="sm:hidden text-[9px] font-semibold text-[#00786F] dark:text-primary">
                Docker Sandbox + 4/4 Pytest + Oral GIL
              </p>
              <p className="hidden sm:block text-xs text-muted-foreground leading-relaxed">
                Evaluación en contenedores efímeros aislados, análisis estático de complejidad por AST y defensa oral.
              </p>
              <p className="hidden sm:block text-xs font-semibold text-primary pt-2 border-t">
                Prueba clave: CRUD asíncrono con 4/4 Pytest y Whisper
              </p>
            </div>

            {/* Area 2: Music (Node n9217 Mobile / n9033 Desktop) */}
            <div className="rounded-lg sm:rounded-xl border border-[#E3E7E8] dark:border-border sm:shadow-xs bg-white dark:bg-card p-3 sm:p-6 space-y-0.5 sm:space-y-3">
              <div className="hidden sm:flex items-center justify-between">
                <Music className="h-6 w-6 text-primary" />
                <span className="text-[10px] font-mono font-bold tracking-wider text-primary uppercase">
                  ESPECTROGRAMA LIBROSA
                </span>
              </div>
              <h3 className="font-extrabold text-[11px] sm:text-base text-[#090B0C] dark:text-foreground">
                Música & Instrumentos
              </h3>
              <p className="sm:hidden text-[9px] font-semibold text-[#00786F] dark:text-primary">
                Espectrograma Librosa (pitch y tempo)
              </p>
              <p className="hidden sm:block text-xs text-muted-foreground leading-relaxed">
                Procesamiento de audio espectral en tiempo real para verificar afinación de cuerdas, tempo y armonía.
              </p>
              <p className="hidden sm:block text-xs font-semibold text-primary pt-2 border-t">
                Prueba clave: Detección de centésimas de semitono y BPM
              </p>
            </div>

            {/* Area 3: Sports (Node n9220 Mobile / n9040 Desktop) */}
            <div className="rounded-lg sm:rounded-xl border border-[#E3E7E8] dark:border-border sm:shadow-xs bg-white dark:bg-card p-3 sm:p-6 space-y-0.5 sm:space-y-3">
              <div className="hidden sm:flex items-center justify-between">
                <Activity className="h-6 w-6 text-primary" />
                <span className="text-[10px] font-mono font-bold tracking-wider text-primary uppercase">
                  VISIÓN CON OPENCV
                </span>
              </div>
              <h3 className="font-extrabold text-[11px] sm:text-base text-[#090B0C] dark:text-foreground">
                Deportes & Fútbol
              </h3>
              <p className="sm:hidden text-[9px] font-semibold text-[#00786F] dark:text-primary">
                Visión OpenCV (tracking de pose y balón)
              </p>
              <p className="hidden sm:block text-xs text-muted-foreground leading-relaxed">
                Tracking de pose corporal y detección esférica de balón para contar repeticiones y control motriz.
              </p>
              <p className="hidden sm:block text-xs font-semibold text-primary pt-2 border-t">
                Prueba clave: Conteo automático de toques y estabilidad
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 4. CATÁLOGO DE HABILIDADES (SECCIÓN DEDICADA) */}
      <section
        id="catalogo"
        className="scroll-mt-14 sm:scroll-mt-16 min-h-dvh sm:min-h-screen flex flex-col justify-center py-8 sm:py-20 border-t bg-white dark:bg-card"
      >
        <div className="container mx-auto max-w-7xl px-4 sm:px-8 w-full space-y-6 sm:space-y-10">
          <div className="text-center space-y-1.5 sm:space-y-3">
            <span className="text-[10px] sm:text-xs font-extrabold uppercase tracking-widest text-[#00786F] dark:text-primary">
              EXPLORÁ EL CATÁLOGO MAESTRO
            </span>
            <h2 className="text-base sm:text-3xl font-black tracking-tight text-[#090B0C] dark:text-foreground">
              Categorías de Habilidades Disponibles
            </h2>
            <p className="text-[11px] sm:text-sm text-[#67787C] dark:text-muted-foreground max-w-xl mx-auto leading-relaxed">
              Encontrá el conocimiento exacto que querés aprender o publicá tu habilidad con acreditación objetiva por IA.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 sm:gap-6">
            {/* Category 1 */}
            <div className="rounded-lg sm:rounded-xl border border-[#E3E7E8] dark:border-border bg-[#F8FAFB] dark:bg-muted/30 p-3.5 sm:p-6 space-y-2">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-md bg-[#00786F]/10 text-[#00786F]">
                  <Code2 className="h-4 w-4 sm:h-5 sm:s-5" />
                </div>
                <h3 className="font-bold text-xs sm:text-base text-[#090B0C] dark:text-foreground">
                  Tecnología & Software
                </h3>
              </div>
              <p className="text-[10px] sm:text-xs text-[#67787C] dark:text-muted-foreground">
                Python, Rust, FastAPI, React, Flutter, Docker y Algoritmos.
              </p>
              <span className="inline-block text-[9px] font-semibold text-[#00786F] dark:text-primary pt-1">
                Niveles 1 al 5 · Sandbox Docker
              </span>
            </div>

            {/* Category 2 */}
            <div className="rounded-lg sm:rounded-xl border border-[#E3E7E8] dark:border-border bg-[#F8FAFB] dark:bg-muted/30 p-3.5 sm:p-6 space-y-2">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-md bg-[#00786F]/10 text-[#00786F]">
                  <Music className="h-4 w-4 sm:h-5 sm:s-5" />
                </div>
                <h3 className="font-bold text-xs sm:text-base text-[#090B0C] dark:text-foreground">
                  Música & Instrumentos
                </h3>
              </div>
              <p className="text-[10px] sm:text-xs text-[#67787C] dark:text-muted-foreground">
                Guitarra, Piano, Batería, Armonía, Mezcla y Solfeo.
              </p>
              <span className="inline-block text-[9px] font-semibold text-[#00786F] dark:text-primary pt-1">
                Pitch y tempo espectral
              </span>
            </div>

            {/* Category 3 */}
            <div className="rounded-lg sm:rounded-xl border border-[#E3E7E8] dark:border-border bg-[#F8FAFB] dark:bg-muted/30 p-3.5 sm:p-6 space-y-2">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-md bg-[#00786F]/10 text-[#00786F]">
                  <Globe className="h-4 w-4 sm:h-5 sm:s-5" />
                </div>
                <h3 className="font-bold text-xs sm:text-base text-[#090B0C] dark:text-foreground">
                  Idiomas & Expresión
                </h3>
              </div>
              <p className="text-[10px] sm:text-xs text-[#67787C] dark:text-muted-foreground">
                Inglés técnico, Francés, Portugués, Oratoria y Comunicación.
              </p>
              <span className="inline-block text-[9px] font-semibold text-[#00786F] dark:text-primary pt-1">
                Validación oral Whisper
              </span>
            </div>

            {/* Category 4 */}
            <div className="rounded-lg sm:rounded-xl border border-[#E3E7E8] dark:border-border bg-[#F8FAFB] dark:bg-muted/30 p-3.5 sm:p-6 space-y-2">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-md bg-[#00786F]/10 text-[#00786F]">
                  <Activity className="h-4 w-4 sm:h-5 sm:s-5" />
                </div>
                <h3 className="font-bold text-xs sm:text-base text-[#090B0C] dark:text-foreground">
                  Deportes & Motricidad
                </h3>
              </div>
              <p className="text-[10px] sm:text-xs text-[#67787C] dark:text-muted-foreground">
                Fútbol, Control motriz, Postura, Yoga y Fitness funcional.
              </p>
              <span className="inline-block text-[9px] font-semibold text-[#00786F] dark:text-primary pt-1">
                Pose tracking OpenCV
              </span>
            </div>
          </div>

          <div className="text-center pt-2">
            <Button
              variant="outline"
              size="sm"
              asChild
              className="text-xs font-semibold text-[#00786F] border-[#00786F]/30 hover:bg-[#00786F]/10"
            >
              <Link to="/app" className="flex items-center gap-1.5">
                <span>Ver Catálogo Completo en la Plataforma</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </Button>
          </div>
        </div>
      </section>

      {/* 5. CONFIANZA & ESCROW (SECCIÓN DEDICADA) */}
      <section
        id="confianza"
        className="scroll-mt-14 sm:scroll-mt-16 min-h-dvh sm:min-h-screen flex flex-col justify-center py-8 sm:py-20 border-t bg-[#F8FAFB] dark:bg-muted/20"
      >
        <div className="container mx-auto max-w-7xl px-4 sm:px-8 w-full space-y-6 sm:space-y-10">
          <div className="text-center space-y-1.5 sm:space-y-3">
            <span className="text-[10px] sm:text-xs font-extrabold uppercase tracking-widest text-[#00786F] dark:text-primary">
              PROTECCIÓN TOTAL SIN RIESGO
            </span>
            <h2 className="text-base sm:text-3xl font-black tracking-tight text-[#090B0C] dark:text-foreground">
              Confianza & Contratos en Custodia Escrow
            </h2>
            <p className="text-[11px] sm:text-sm text-[#67787C] dark:text-muted-foreground max-w-xl mx-auto leading-relaxed">
              Tus horas y SkillPoints siempre asegurados. Ninguna clase se pierde y no hay pagos por adelantado a terceros.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5 sm:gap-6">
            {/* Pillar 1 */}
            <div className="rounded-lg sm:rounded-xl border border-[#E3E7E8] dark:border-border bg-white dark:bg-card p-4 sm:p-6 space-y-2">
              <div className="p-2 w-fit rounded-lg bg-[#00786F]/10 text-[#00786F]">
                <ShieldCheck className="h-5 w-5" />
              </div>
              <h3 className="font-bold text-xs sm:text-base text-[#090B0C] dark:text-foreground">
                1. Custodia Automática en Escrow
              </h3>
              <p className="text-[10px] sm:text-xs text-[#67787C] dark:text-muted-foreground leading-relaxed">
                Al confirmar la propuesta, los SkillPoints se depositan en una bóveda temporal segura. Nadie cobra hasta que la clase se concrete.
              </p>
              <p className="text-[9px] font-semibold text-[#00786F] dark:text-primary pt-1">
                Fondos retenidos sin riesgo de estafa
              </p>
            </div>

            {/* Pillar 2 */}
            <div className="rounded-lg sm:rounded-xl border border-[#E3E7E8] dark:border-border bg-white dark:bg-card p-4 sm:p-6 space-y-2">
              <div className="p-2 w-fit rounded-lg bg-[#00786F]/10 text-[#00786F]">
                <KeyRound className="h-5 w-5" />
              </div>
              <h3 className="font-bold text-xs sm:text-base text-[#090B0C] dark:text-foreground">
                2. Validación Mutua de Encuentro
              </h3>
              <p className="text-[10px] sm:text-xs text-[#67787C] dark:text-muted-foreground leading-relaxed">
                En presencial, validás la sesión intercambiando el PIN mutuo de 4 dígitos. En virtual, el temporizador WebRTC sincronizado audita la asistencia.
              </p>
              <p className="text-[9px] font-semibold text-[#00786F] dark:text-primary pt-1">
                PIN mutuo y auditoría sincronizada
              </p>
            </div>

            {/* Pillar 3 */}
            <div className="rounded-lg sm:rounded-xl border border-[#E3E7E8] dark:border-border bg-white dark:bg-card p-4 sm:p-6 space-y-2">
              <div className="p-2 w-fit rounded-lg bg-[#00786F]/10 text-[#00786F]">
                <Scale className="h-5 w-5" />
              </div>
              <h3 className="font-bold text-xs sm:text-base text-[#090B0C] dark:text-foreground">
                3. Arbitraje y Reembolso 100%
              </h3>
              <p className="text-[10px] sm:text-xs text-[#67787C] dark:text-muted-foreground leading-relaxed">
                Si la contraparte no se presenta o surge una disputa justificada, el centro de quejas resuelve en 24h reintegrando el 100% de los puntos a tu billetera.
              </p>
              <p className="text-[9px] font-semibold text-[#00786F] dark:text-primary pt-1">
                Resolución y reembolso garantizado
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 6. MÉTRICAS CONSOLIDADAS DE LA COMUNIDAD (Node n9223 Mobile / n9047 Desktop) */}
      <section
        id="metricas"
        className="scroll-mt-14 sm:scroll-mt-16 min-h-dvh sm:min-h-screen flex flex-col justify-center py-8 sm:py-20 border-y bg-[#E6F4F2] dark:bg-primary/10"
      >
        <div className="container mx-auto max-w-7xl px-4 sm:px-8 text-center space-y-3.5 sm:space-y-12 w-full">
          <h2 className="text-sm sm:text-sm font-black uppercase tracking-widest text-[#00786F] dark:text-primary">
            <span className="sm:hidden">MÉTRICAS DE LA COMUNIDAD</span>
            <span className="hidden sm:inline">MÉTRICAS CONSOLIDADAS DE LA COMUNIDAD</span>
          </h2>

          {/* Mobile direct single-line text layout (Nodes n9225, n9226, n9227) */}
          <div className="sm:hidden flex flex-col items-center space-y-3 text-[12px] font-bold text-[#090B0C] dark:text-foreground">
            <p>4,850+ Horas de Clase Realizadas</p>
            <p>98.4% Satisfacción de Alumnos</p>
            <p>100% Depósitos en Escrow</p>
          </div>

          {/* Desktop 4-column cards layout */}
          <div className="hidden sm:grid grid-cols-2 lg:grid-cols-4 gap-8">
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
      <section className="min-h-dvh sm:min-h-screen flex flex-col justify-center py-16 sm:py-24 container mx-auto max-w-4xl px-4 sm:px-8 text-center space-y-4 sm:space-y-5">
        <h2 className="text-2xl sm:text-4xl font-extrabold text-[#090B0C] dark:text-foreground tracking-tight">
          Unite a la red de intercambio formativo más confiable
        </h2>
        <p className="text-xs sm:text-sm text-[#67787C] dark:text-muted-foreground max-w-xl mx-auto leading-relaxed">
          Registrate gratis hoy y obtené tus 3 primeras validaciones técnicas supervisadas por IA sin costo.
        </p>
        <div className="pt-2">
          <Button
            size="lg"
            asChild
            className="w-full sm:w-auto bg-[#00786F] hover:bg-[#00786F]/90 text-[#F0FDFA] font-bold h-11 sm:h-12 px-8 text-xs sm:text-sm rounded-lg shadow-sm"
          >
            <Link to="/app" className="flex items-center justify-center gap-2">
              <span>Crear Cuenta Gratuita en 1 Clic</span>
              <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        </div>
      </section>
    </div>
  )
}

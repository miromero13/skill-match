import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { ArrowLeft, ArrowRight, BookOpen, Check, Clock3, ShieldCheck } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useEvaluationPreflightStore } from "@/stores/evaluation-preflight-store"
import { browserSupervisionTrialEnabled } from "@/lib/feature-flags"
import { CalibrationPanel } from "@/components/evaluations/calibration-panel"

const steps = [
  { short: "Habilidad", title: "Habilidad a validar" },
  { short: "Normas", title: "Normas de integridad" },
  { short: "Calibrar", title: "Calibración en vivo" },
]

export function EvaluationSetupPage() {
  const { skillId } = useParams<{ skillId: string }>()
  const { preflight, consent, loading, saving, error, load, accept, reset } = useEvaluationPreflightStore()
  const [step, setStep] = useState(1)
  const [reviewing, setReviewing] = useState(false)
  const [biometric, setBiometric] = useState(false)
  const [integrity, setIntegrity] = useState(false)
  const [attemptRule, setAttemptRule] = useState(false)
  const currentStep = consent && !reviewing ? 3 : step

  useEffect(() => {
    if (skillId) void load(skillId)
    return reset
  }, [skillId, load, reset])

  async function continueToCalibration() {
    await accept()
    if (!useEvaluationPreflightStore.getState().error) setReviewing(false)
  }

  return <section className="min-h-[calc(100dvh-4rem)] bg-muted/25 px-4 py-4 sm:px-6 lg:grid lg:place-items-center lg:py-12" aria-label="Preparación de evaluación">
    <Card className="mx-auto w-full max-w-[900px] rounded-2xl border bg-card py-0 shadow-none ring-0">
      <CardContent className="gap-5 p-3 sm:p-8">
        {loading && <p role="status" className="py-8 text-center text-muted-foreground">Consultando requisitos…</p>}
        {error && <div role="alert" className="space-y-3 rounded-xl border border-destructive/30 bg-destructive/5 p-4">
          <p>{error}</p>
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline"><Link to="/app/profile">Ir a mi perfil</Link></Button>
            {!preflight && <Button variant="outline" onClick={() => { if (skillId) void load(skillId) }}>Reintentar</Button>}
          </div>
        </div>}
        {preflight && <>
          <h1 className="sr-only">Validar {preflight.skill_name}</h1>
          <nav aria-label="Pasos del pre-embarque" className="rounded-xl bg-muted p-1">
            <ol className="grid grid-cols-3 gap-1">
              {steps.map((item, index) => {
                const number = index + 1
                const complete = currentStep > number
                const active = currentStep === number
                return <li key={item.short} aria-current={active ? "step" : undefined}
                  className={`flex min-w-0 items-center justify-center gap-1.5 rounded-lg px-1 py-3 text-[11px] font-semibold sm:gap-2 sm:px-3 sm:text-xs ${active ? "bg-card text-primary shadow-xs" : complete ? "text-foreground" : "text-muted-foreground"}`}>
                  <span className={`flex size-5 shrink-0 items-center justify-center rounded-full text-[10px] ${active ? "bg-primary text-primary-foreground" : complete ? "bg-emerald-500 text-white" : "bg-border text-muted-foreground"}`}>
                    {complete ? <Check className="size-3.5" aria-hidden="true" /> : number}
                  </span>
                  <span className="sm:hidden">{number}. {item.short}</span>
                  <span className="hidden sm:inline">{number}. {item.title}</span>
                </li>
              })}
            </ol>
          </nav>
          <p className="sr-only">Paso {currentStep} de 3</p>
          {currentStep === 3 && consent ? <>
            <p className="sr-only">Consentimiento registrado</p>
            <CalibrationPanel key={consent.id} evaluationId={consent.id} targetLevel={preflight.target_level_number} onBack={() => { setStep(2); setReviewing(true) }} />
            <p className="text-xs text-muted-foreground">El intento todavía no comenzó ni se descontó.</p>
          </> : step === 1 ? <>
            <Card className="rounded-xl border bg-muted/20 py-0 shadow-none ring-0">
              <CardContent className="gap-4 p-4 sm:p-5">
                <h2 className="text-xs leading-relaxed font-bold text-primary uppercase">Paso 1 de 3: instrucciones generales</h2>
                <p className="text-xs leading-relaxed text-muted-foreground">Revisá la habilidad y el nivel declarados en tu perfil, junto con las condiciones antes de continuar con las normas de integridad.</p>
                <div className="grid gap-4 sm:grid-cols-3">
                  <div className="space-y-1.5"><Label htmlFor="evaluation-skill" className="text-[11px] font-bold text-muted-foreground uppercase">Habilidad declarada en tu perfil</Label>
                    <Input id="evaluation-skill" value={preflight.skill_name} readOnly disabled className="h-11 border-primary bg-card font-semibold disabled:opacity-100 disabled:cursor-default" /></div>
                  <div className="space-y-1.5"><Label htmlFor="evaluation-level" className="text-[11px] font-bold text-muted-foreground uppercase">Nivel objetivo a validar</Label>
                    <Input id="evaluation-level" value={preflight.declared_level_label ?? `Nivel ${preflight.target_level_number ?? 1} · Principiante`} readOnly disabled className="h-11 border-primary/50 bg-card font-semibold text-primary disabled:opacity-100 disabled:cursor-default" /></div>
                  <div className="space-y-1.5"><Label htmlFor="evaluation-duration" className="text-[11px] font-bold text-muted-foreground uppercase">Duración estimada</Label>
                    <Input id="evaluation-duration" value={`${preflight.estimated_duration_minutes ?? 20} minutos`} readOnly disabled className="h-11 bg-card font-medium disabled:opacity-100 disabled:cursor-default" /></div>
                </div>
                <div className="space-y-2 border-t pt-4">
                  <h3 className="flex items-center gap-2 text-sm font-semibold"><BookOpen className="size-4 text-primary" aria-hidden="true" />Temario de la prueba</h3>
                  <p className="text-sm text-muted-foreground">{preflight.syllabus}</p>
                  <ol className="flex flex-wrap gap-2">{preflight.stages.map((stage, index) => <li key={stage} className="rounded-md border bg-card px-2.5 py-1.5 text-xs">{index + 1}. <span>{stage}</span></li>)}</ol>
                </div>
                <div className="space-y-2"><h3 className="text-sm font-semibold">Requisitos del ambiente</h3>
                  <ul className="list-inside list-disc space-y-1 text-xs leading-relaxed text-muted-foreground">{preflight.requirements.map(item => <li key={item}>{item}</li>)}</ul>
                </div>
                {preflight.estimated_duration_minutes === null && <p className="flex items-start gap-2 text-xs text-muted-foreground"><Clock3 className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />La duración deberá informarse antes del inicio del examen.</p>}
              </CardContent>
            </Card>
            <div className="flex flex-col-reverse justify-between gap-3 sm:flex-row sm:items-center">
              <Button asChild variant="outline" className="h-11"><Link to="/app/teaching-skills"><ArrowLeft aria-hidden="true" />Volver a mis habilidades</Link></Button>
              <Button className="h-11 sm:px-6" onClick={() => setStep(2)}>Siguiente: normas de integridad<ArrowRight aria-hidden="true" /></Button>
            </div>
          </> : <>
            <Card className="rounded-xl border bg-muted/20 py-0 shadow-none ring-0">
              <CardContent className="gap-4 p-4 sm:p-5">
                <h2 className="text-xs leading-relaxed font-bold text-primary uppercase">Paso 2 de 3: normas obligatorias de integridad y supervisión</h2>
                <p className="text-xs leading-relaxed text-muted-foreground">Leé los requisitos antes de pasar a la calibración de cámara y micrófono.</p>
                <ul className="space-y-2 text-xs leading-relaxed text-muted-foreground marker:text-primary">
                  <li><strong className="text-foreground">Cámara y micrófono disponibles.</strong> Prepará un ambiente iluminado y un rostro visible, centrado y sin obstrucciones.</li>
                  <li><strong className="text-foreground">Una sola persona y sin ayuda externa.</strong> La teoría, la práctica y la defensa deben realizarse de forma individual.</li>
                  <li><strong className="text-foreground">Sin copiar soluciones.</strong> Los cambios de pestaña y las acciones del portapapeles podrán registrarse como incidentes durante la evaluación.</li>
                  <li><strong className="text-foreground">Procesamiento propio y corrección textual.</strong> Se utilizarán cámara y micrófono para comprobar el ambiente y cotejar tu identidad con el rostro enrolado; la transcripción de tus respuestas teóricas se evaluará con el corrector configurado sin enviar audio, video ni datos de cuenta.</li>
                </ul>
                <div className="flex items-start gap-2 rounded-lg border border-primary/15 bg-primary/5 p-3 text-xs leading-relaxed text-primary"><ShieldCheck className="mt-0.5 size-4 shrink-0" aria-hidden="true" /><p>Habilidades gratuitas disponibles: {preflight.free_evaluations_left}/3 · Intentos utilizados para esta habilidad: {preflight.attempts_used}/1</p></div>
                <div className="space-y-3 rounded-lg bg-primary/5 p-3">
                  <div className="flex items-start gap-3"><Checkbox id="biometric-consent" checked={biometric} disabled={saving} onCheckedChange={value => setBiometric(value === true)} />
                    <Label className="text-xs leading-relaxed" htmlFor="biometric-consent">Acepto el procesamiento biométrico, el uso de cámara y micrófono, y el envío de transcripciones textuales (sin audio ni datos personales) para su corrección.</Label></div>
                  <div className="flex items-start gap-3"><Checkbox id="integrity-consent" checked={integrity} disabled={saving} onCheckedChange={value => setIntegrity(value === true)} />
                    <Label className="text-xs leading-relaxed" htmlFor="integrity-consent">Acepto las normas de integridad y la supervisión durante las tres etapas.</Label></div>
                  <div className="flex items-start gap-3"><Checkbox id="attempt-rule" checked={attemptRule} disabled={saving} onCheckedChange={value => setAttemptRule(value === true)} />
                    <Label className="text-xs leading-relaxed" htmlFor="attempt-rule">Entiendo que al comenzar el examen el intento se consume y no se devuelve.</Label></div>
                </div>
                <p className="text-xs leading-relaxed text-muted-foreground">El intento se descuenta de forma definitiva al comenzar efectivamente el examen, después de la comprobación del ambiente. Abandonar después no lo devuelve. Versión de condiciones: {preflight.policy_version}.</p>
              </CardContent>
            </Card>
            <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-between">
              <Button variant="outline" className="h-auto min-h-11 whitespace-normal py-2" disabled={saving} onClick={() => setStep(1)}><ArrowLeft aria-hidden="true" />Volver a instrucciones</Button>
              <Button className="h-auto min-h-11 whitespace-normal py-2 sm:px-6" disabled={!biometric || !integrity || !attemptRule || saving} onClick={() => void continueToCalibration()}>
                {saving ? "Registrando…" : "Registrar consentimiento"}<ArrowRight aria-hidden="true" />
              </Button>
            </div>
          </>}
          <p className="text-xs leading-relaxed text-muted-foreground">Leer las instrucciones y aceptar el consentimiento no consume tu intento.</p>
          {browserSupervisionTrialEnabled && (
            <Button asChild variant="outline">
              <Link
                to="/app/browser-supervision-test"
                state={{ autoStart: true }}
                onClick={() => {
                  void document.documentElement.requestFullscreen?.().catch(() => undefined)
                }}
              >
                Probar controles del navegador (SM-43, sin examen)
              </Link>
            </Button>
          )}
          {currentStep !== 2 && <p className="text-xs text-muted-foreground">Habilidades gratuitas disponibles: {preflight.free_evaluations_left}/3 · Intentos utilizados para esta habilidad: {preflight.attempts_used}/1</p>}
        </>}
      </CardContent>
    </Card>
  </section>
}

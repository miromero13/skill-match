import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { useEvaluationPreflightStore } from "@/stores/evaluation-preflight-store"
import { CalibrationPanel } from "@/components/evaluations/calibration-panel"

export function EvaluationSetupPage() {
  const { skillId } = useParams<{ skillId: string }>()
  const { preflight, consent, loading, saving, error, load, accept, reset } = useEvaluationPreflightStore()
  const [step, setStep] = useState(1)
  const [biometric, setBiometric] = useState(false)
  const [integrity, setIntegrity] = useState(false)
  const [attemptRule, setAttemptRule] = useState(false)

  useEffect(() => {
    if (skillId) void load(skillId)
    return reset
  }, [skillId, load, reset])

  return <section className="mx-auto w-full max-w-3xl space-y-5 p-4 md:p-6" aria-label="Preparación de evaluación">
    <Button asChild variant="link"><Link to="/app/teaching-skills">Volver a mis habilidades</Link></Button>
    {loading && <p role="status">Consultando requisitos…</p>}
    {error && <div role="alert" className="space-y-3 rounded-lg border border-destructive p-4">
      <p>{error}</p>
      <Button asChild variant="outline"><Link to="/app/profile">Ir a mi perfil</Link></Button>
      {!preflight && <Button variant="outline" onClick={() => { if (skillId) void load(skillId) }}>Reintentar</Button>}
    </div>}
    {preflight && <>
      <h1 className="text-2xl font-semibold">Validar {preflight.skill_name}</h1>
      <p className="text-sm text-muted-foreground">Preparación compartida para todas las habilidades · Paso {step} de 2</p>
      <p>Leer las instrucciones y aceptar el consentimiento no consume tu intento.</p>
      <p>Habilidades gratuitas disponibles: {preflight.free_evaluations_left}/3 · Intentos utilizados para esta habilidad: {preflight.attempts_used}/1</p>
      {consent ? <Card><CardHeader><CardTitle>Consentimiento registrado</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <p>El intento todavía no comenzó ni se descontó.</p>
          <CalibrationPanel key={consent.id} evaluationId={consent.id} />
          <p className="text-sm text-muted-foreground">Estado: {consent.status} · Evaluación: {consent.id}</p>
        </CardContent>
      </Card> : step === 1 ? <Card>
        <CardHeader><CardTitle>Instrucciones generales</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <p>{preflight.syllabus}</p>
          <h2 className="font-medium">Etapas de la evaluación</h2>
          <ol className="list-inside list-decimal space-y-1">{preflight.stages.map(stage => <li key={stage}>{stage}</li>)}</ol>
          <h2 className="font-medium">Requisitos del ambiente</h2>
          <ul className="list-inside list-disc space-y-1">{preflight.requirements.map(item => <li key={item}>{item}</li>)}</ul>
          <p>{preflight.estimated_duration_minutes === null
            ? "Duración: pendiente de configurar para esta prueba; deberá informarse antes del inicio."
            : `Duración estimada: ${preflight.estimated_duration_minutes} minutos.`}</p>
          <Button onClick={() => setStep(2)}>Siguiente: normas de integridad</Button>
        </CardContent>
      </Card> : <Card>
        <CardHeader><CardTitle>Normas de integridad y consentimiento</CardTitle></CardHeader>
        <CardContent className="space-y-5">
          <p>La teoría, la práctica y la defensa se realizan con supervisión. No se permite ayuda externa ni copiar soluciones. Los cambios de pestaña y las acciones del portapapeles podrán registrarse como incidentes.</p>
          <p>Se utilizarán cámara y micrófono para comprobar el ambiente, verificar tu identidad frente al rostro enrolado y supervisar la evaluación con procesamiento propio.</p>
          <p>Al comenzar efectivamente el examen, después de la comprobación del ambiente, el intento se descuenta de forma definitiva. Abandonar después no lo devuelve.</p>
          <div className="flex items-start gap-3"><Checkbox id="biometric-consent" checked={biometric} disabled={saving} onCheckedChange={value => setBiometric(value === true)} />
            <Label htmlFor="biometric-consent">Acepto el procesamiento biométrico y el uso de cámara y micrófono para esta evaluación.</Label></div>
          <div className="flex items-start gap-3"><Checkbox id="integrity-consent" checked={integrity} disabled={saving} onCheckedChange={value => setIntegrity(value === true)} />
            <Label htmlFor="integrity-consent">Acepto las normas de integridad y la supervisión durante las tres etapas.</Label></div>
          <div className="flex items-start gap-3"><Checkbox id="attempt-rule" checked={attemptRule} disabled={saving} onCheckedChange={value => setAttemptRule(value === true)} />
            <Label htmlFor="attempt-rule">Entiendo que al comenzar el examen el intento se consume y no se devuelve.</Label></div>
          <p className="text-sm text-muted-foreground">Versión de condiciones: {preflight.policy_version}</p>
          <div className="flex flex-wrap gap-3">
            <Button variant="outline" disabled={saving} onClick={() => setStep(1)}>Volver a instrucciones</Button>
            <Button disabled={!biometric || !integrity || !attemptRule || saving} onClick={() => void accept()}>
              {saving ? "Registrando…" : "Registrar consentimiento"}
            </Button>
          </div>
        </CardContent>
      </Card>}
    </>}
  </section>
}

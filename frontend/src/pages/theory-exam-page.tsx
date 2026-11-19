import { useCallback, useEffect, useRef, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { theoryExam, type OralSubmission } from "@/services/theory-exam-service"
import { useTheoryExamStore } from "@/stores/theory-exam-store"
import { startOralRecording, type OralRecording } from "@/services/oral-recording"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Progress } from "@/components/ui/progress"
import { ApiError } from "@/types/api"

const messageOf = (error: unknown) => error instanceof Error ? error.message : "No se pudo completar la operación."
const levels = ["Principiante", "Elemental", "Intermedio", "Avanzado", "Master Pedagogo"]

export function TheoryExamPage() {
  const { id = "" } = useParams()
  const progress = useTheoryExamStore(state => state.progress)
  const setProgress = useTheoryExamStore(state => state.setProgress)
  const state = progress?.evaluation_id === id ? progress : null
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")
  const [busy, setBusy] = useState(false)
  const [level, setLevel] = useState("1")
  const [textConsent, setTextConsent] = useState(false)
  const [recording, setRecording] = useState(false)
  const [retryReady, setRetryReady] = useState(false)
  const [remaining, setRemaining] = useState(0)
  const alive = useRef(false)
  const capture = useRef<OralRecording | null>(null)
  const captureAbort = useRef<AbortController | null>(null)
  const pending = useRef<OralSubmission | null>(null)
  const serverOffset = useRef(0)
  const recordingQuestion = useRef("")
  const activeId = useRef(id)
  activeId.current = id
  const refresh = useCallback(async () => {
    const result = await theoryExam.status(id)
    if (!alive.current || activeId.current !== id) return
    serverOffset.current = Date.parse(result.data.server_time) - Date.now()
    setProgress(result.data)
  }, [id, setProgress])
  useEffect(() => {
    alive.current = true
    setProgress(null)
    setError("")
    void refresh().catch(reason => { if (alive.current) setError(messageOf(reason)) })
    const interval = setInterval(() => { void refresh().catch(reason => { if (alive.current) setError(messageOf(reason)) }) }, 5000)
    return () => {
      alive.current = false; clearInterval(interval)
      captureAbort.current?.abort(); capture.current?.cancel(); capture.current = null
      pending.current = null; setProgress(null)
    }
  }, [refresh, setProgress])
  useEffect(() => {
    const update = () => setRemaining(state?.question_deadline_at
      ? Math.max(0, Math.ceil((Date.parse(state.question_deadline_at) - Date.now() - serverOffset.current) / 1000)) : 0)
    update()
    const timer = setInterval(update, 250)
    return () => clearInterval(timer)
  }, [state?.question_deadline_at])
  useEffect(() => {
    if (recording && (state?.current_question?.id !== recordingQuestion.current || remaining === 0)) {
      captureAbort.current?.abort(); capture.current = null; setRecording(false)
      setError("La pregunta venció o cambió. La captura se canceló; consultá el estado del examen.")
    }
  }, [recording, state, remaining])
  useEffect(() => {
    if (!state?.current_question) return
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = "" }
    window.addEventListener("beforeunload", warn)
    return () => window.removeEventListener("beforeunload", warn)
  }, [state?.current_question])
  const enterExamFullscreen = () => {
    if (!document.fullscreenElement) void document.documentElement.requestFullscreen?.().catch(() => undefined)
  }
  const run = async (operation: () => Promise<void>) => {
    if (busy) return
    setBusy(true); setError("")
    try { await operation() } catch (reason) { if (alive.current) setError(messageOf(reason)) }
    finally { if (alive.current) setBusy(false) }
  }
  const record = () => void run(async () => {
    if (!state?.current_question || remaining <= 0 || pending.current) return
    const controller = new AbortController()
    captureAbort.current = controller
    recordingQuestion.current = state.current_question.id
    const acquired = await startOralRecording(controller.signal, text => {
      if (alive.current) { setRecording(false); setError(text); capture.current = null }
    })
    if (!alive.current || controller.signal.aborted) { acquired.cancel(); return }
    capture.current = acquired; setRecording(true)
  })
  const send = () => void run(async () => {
    if (!pending.current && capture.current) {
      const current = capture.current
      capture.current = null; setRecording(false)
      pending.current = { submission_id: crypto.randomUUID(), question_id: recordingQuestion.current, audio_base64: await current.stop() }
      setRetryReady(true)
    }
    if (!pending.current) return
    let result
    try {
      result = await theoryExam.answer(id, pending.current)
    } catch (reason) {
      if (reason instanceof ApiError && [409, 410].includes(reason.statuscode)) {
        pending.current = null
        if (alive.current) setRetryReady(false)
      }
      throw reason
    }
    if (!alive.current) return
    pending.current = null; setRetryReady(false); setNotice(result.message)
    await refresh()
  })
  const examActive = Boolean(state)
  return <main className={examActive
    ? "grid min-h-screen w-full gap-5 bg-background p-4 sm:p-8"
    : "mx-auto grid min-h-screen max-w-5xl gap-5 p-4 sm:p-8"}>
    <header><h1 className="text-2xl font-semibold">Evaluación teórica oral</h1><p>Respondé hablando y justificá tu elección, incluso en preguntas de opción múltiple.</p></header>
    {error && <p role="alert" className="text-destructive">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    {!state && <Card><CardHeader><CardTitle>Antes de comenzar</CardTitle></CardHeader><CardContent className="grid gap-4">
      <p>El inicio consume tu intento una sola vez. Se requieren calibración, preguntas publicadas y transcripción local disponible.</p>
      <div className="flex items-start gap-3"><Checkbox id="theory-text-consent" checked={textConsent} onCheckedChange={value => setTextConsent(value === true)} />
        <Label htmlFor="theory-text-consent">Autorizo enviar al proveedor configurado la pregunta, referencia, rúbrica y transcripción de mis respuestas para corregirlas. No se enviará audio, video, nombre ni datos de cuenta.</Label></div>
      <Label htmlFor="theory-level">Nivel a evaluar</Label><Select value={level} disabled={busy} onValueChange={setLevel}><SelectTrigger id="theory-level"><SelectValue /></SelectTrigger><SelectContent>{levels.map((name, index) => <SelectItem key={name} value={String(index + 1)}>{name}</SelectItem>)}</SelectContent></Select>
      <Button disabled={busy || !textConsent} onClick={() => { enterExamFullscreen(); void run(async () => { const response = await theoryExam.start(id, Number(level), textConsent); if (alive.current) { setNotice(response.message); await refresh() } }) }}>Comenzar examen y consumir intento</Button>
    </CardContent></Card>}
    {state?.current_question && <div className="grid min-h-[calc(100vh-8rem)] gap-5">
      <Card><CardHeader><CardTitle>Pregunta {state.position} de {state.question_count}</CardTitle><Progress value={state.answered_count / state.question_count * 100} aria-label="Progreso del examen" /></CardHeader><CardContent className="grid gap-4">
        <p className="text-lg">{state.current_question.prompt}</p>
        {state.current_question.choices.map(choice => <p key={choice.code}>{choice.code}: {choice.text}</p>)}
        <p role="timer">Tiempo aproximado restante: {remaining}s. El servidor determina el vencimiento.</p>
        <Button disabled={busy || recording || retryReady || remaining <= 0} onClick={record}>Grabar respuesta</Button>
        {recording && <p role="status">Micrófono grabando. Terminá y enviá tu explicación antes del vencimiento.</p>}
        <Button disabled={busy || (!recording && !retryReady)} onClick={send}>{retryReady ? "Reenviar misma respuesta" : "Terminar y enviar respuesta"}</Button>
        {recording && <Button variant="outline" disabled={busy} onClick={() => { captureAbort.current?.abort(); capture.current = null; setRecording(false) }}>Cancelar grabación</Button>}
        <p className="text-sm text-muted-foreground">Audio en memoria únicamente; máximo90s por grabación. Si falla el envío, reenviá la misma respuesta sin volver a grabar. Salir de esta página descarta audio pendiente, pero no devuelve el intento.</p>
      </CardContent></Card>
    </div>}
    {state && !state.current_question && <Card><CardHeader><CardTitle>{state.grading_state === "COMPLETE" ? "Resultado de la corrección" : "Corrección teórica"}</CardTitle></CardHeader><CardContent className="grid gap-3">
      <p>{state.answered_count} de {state.question_count} respuestas registradas.</p>
      {state.grading_state === "COMPLETE" ? <><p>Resultado: {state.grading_score} puntos. La nota ponderada usa la rúbrica publicada.</p>
        {state.grading_feedback?.map(item => <section key={item.question_id}><h2 className="font-medium">Pregunta · {item.points}/{item.max_score}</h2><p>{item.feedback}</p>
          {item.criteria.map(criterion => <p key={criterion.name}>{criterion.name}: {criterion.attainment * 100}% — {criterion.reason}</p>)}</section>)}</>
        : <><p>{state.grading_state === "ERROR" ? "La corrección no pudo completarse; no se asignó nota. Tus respuestas permanecen guardadas." : "Corrección pendiente; todavía no se asignó nota."}</p>
          <Button disabled={busy} onClick={() => void run(async () => { const response = await theoryExam.retryGrading(id); setNotice(response.message); await refresh() })}>{state.grading_state === "ERROR" ? "Reintentar corrección" : "Solicitar corrección"}</Button></>}
      <p className="text-sm text-muted-foreground">No se emite sello ni certificado automático.</p>
      {(state.status === "THEORY_PENDING_REVIEW" || state.grading_state === "COMPLETE" || state.grading_state === "ERROR") && <Link to={`/evaluation/${id}/code`}><Button variant="outline">Continuar a la evaluación práctica</Button></Link>}
    </CardContent></Card>}
    <Button variant="outline" disabled={busy} onClick={() => void run(refresh)}>Actualizar estado</Button>
  </main>
}

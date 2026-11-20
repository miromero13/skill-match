import { useCallback, useEffect, useRef, useState } from "react"
import { useNavigate, useParams, useSearchParams } from "react-router-dom"
import { theoryExam, type OralSubmission } from "@/services/theory-exam-service"
import { useTheoryExamStore } from "@/stores/theory-exam-store"
import { useEvaluationPreflightStore } from "@/stores/evaluation-preflight-store"
import { startOralRecording, type OralRecording } from "@/services/oral-recording"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { ApiError } from "@/types/api"

const messageOf = (error: unknown) => error instanceof Error ? error.message : "No se pudo completar la operación."

export function TheoryExamPage() {
  const { id = "" } = useParams()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const preflight = useEvaluationPreflightStore(state => state.preflight)
  const progress = useTheoryExamStore(state => state.progress)
  const setProgress = useTheoryExamStore(state => state.setProgress)
  const state = progress?.evaluation_id === id ? progress : null
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")
  const [busy, setBusy] = useState(false)
  const [starting, setStarting] = useState(true)
  const queryLevel = Number(searchParams.get("level") || "")
  const targetLevelNumber =
    queryLevel >= 1 && queryLevel <= 5
      ? queryLevel
      : preflight?.target_level_number ?? 1
  const [recording, setRecording] = useState(false)
  const [retryReady, setRetryReady] = useState(false)
  const [remaining, setRemaining] = useState(0)
  const alive = useRef(false)
  const startedOnce = useRef(false)
  const capture = useRef<OralRecording | null>(null)
  const captureAbort = useRef<AbortController | null>(null)
  const pending = useRef<OralSubmission | null>(null)
  const serverOffset = useRef(0)
  const recordingQuestion = useRef("")
  const activeId = useRef(id)
  activeId.current = id

  const enterExamFullscreen = () => {
    if (!document.fullscreenElement) void document.documentElement.requestFullscreen?.().catch(() => undefined)
  }

  const exitExamFullscreen = () => {
    if (document.fullscreenElement) void document.exitFullscreen?.().catch(() => undefined)
  }

  const refresh = useCallback(async () => {
    const result = await theoryExam.status(id)
    if (!alive.current || activeId.current !== id) return
    serverOffset.current = Date.parse(result.data.server_time) - Date.now()
    setProgress(result.data)
  }, [id, setProgress])

  const initExam = useCallback(async () => {
    setError("")
    setStarting(true)
    try {
      await refresh()
    } catch (reason) {
      if (!alive.current) return
      if (reason instanceof ApiError && reason.statuscode === 409 && !reason.message.includes("cancelada")) {
        if (!startedOnce.current) {
          startedOnce.current = true
          enterExamFullscreen()
          try {
            const started = await theoryExam.start(id, targetLevelNumber, true)
            if (!alive.current) return
            setNotice(started.message)
            await refresh()
            return
          } catch (startErr) {
            if (alive.current) setError(messageOf(startErr))
            return
          }
        }
      }
      setError(messageOf(reason))
    } finally {
      if (alive.current) setStarting(false)
    }
  }, [id, refresh, targetLevelNumber])

  useEffect(() => {
    alive.current = true
    startedOnce.current = false
    setProgress(null)
    void initExam()
    const interval = setInterval(() => {
      void refresh().catch(reason => {
        if (!alive.current) return
        if (reason instanceof ApiError && reason.statuscode === 409 && !reason.message.includes("cancelada")) return
        setError(messageOf(reason))
      })
    }, 5000)
    return () => {
      alive.current = false
      clearInterval(interval)
      captureAbort.current?.abort()
      capture.current?.cancel()
      capture.current = null
      pending.current = null
      setProgress(null)
    }
  }, [initExam, refresh, setProgress])

  useEffect(() => {
    const update = () => setRemaining(state?.question_deadline_at
      ? Math.max(0, Math.ceil((Date.parse(state.question_deadline_at) - Date.now() - serverOffset.current) / 1000)) : 0)
    update()
    const timer = setInterval(update, 250)
    return () => clearInterval(timer)
  }, [state?.question_deadline_at])

  useEffect(() => {
    if (recording && (state?.current_question?.id !== recordingQuestion.current || remaining === 0)) {
      captureAbort.current?.abort()
      capture.current = null
      setRecording(false)
      setError("La pregunta venció o cambió. La captura se canceló; consultá el estado del examen.")
    }
  }, [recording, state, remaining])

  useEffect(() => {
    if (!state?.current_question) return
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = "" }
    window.addEventListener("beforeunload", warn)
    return () => window.removeEventListener("beforeunload", warn)
  }, [state?.current_question])

  useEffect(() => {
    if (state && !state.current_question && state.status !== "CANCELLED") {
      const nextRoute = state.has_coding_stage ? `/evaluation/${id}/code` : `/evaluation/${id}/result`
      navigate(nextRoute, { replace: true })
    }
  }, [state, id, navigate])

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

  const cancelEvaluation = () => void run(async () => {
    captureAbort.current?.abort()
    capture.current?.cancel()
    capture.current = null
    setRecording(false)
    pending.current = null
    await theoryExam.cancel(id)
    exitExamFullscreen()
    navigate("/app/teaching-skills", { replace: true })
  })

  const totalQuestionSeconds = state?.current_question?.time_limit_seconds || 90
  const timePercent = Math.max(0, Math.min(100, (remaining / totalQuestionSeconds) * 100))
  const isLowTime = remaining <= 15 || timePercent <= 20

  return (
    <main className="grid min-h-screen w-full content-start gap-5 bg-background p-4 sm:p-8">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Evaluación teórica oral</h1>
          <p className="text-sm text-muted-foreground">Respondé hablando y justificá tu elección, incluso en preguntas de opción múltiple.</p>
        </div>
        <Button variant="destructive" size="sm" disabled={busy} onClick={cancelEvaluation}>
          Cancelar evaluación
        </Button>
      </header>

      {error && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          <span>{error}</span>
          {!state && (
            <Button size="sm" variant="outline" disabled={busy} onClick={() => { startedOnce.current = false; void initExam() }}>
              Reintentar
            </Button>
          )}
        </div>
      )}
      {notice && <p role="status" className="text-sm text-muted-foreground">{notice}</p>}

      {!state && starting && (
        <Card>
          <CardContent className="py-8 text-center text-sm text-muted-foreground">
            Iniciando evaluación teórica…
          </CardContent>
        </Card>
      )}

      {state?.current_question && (
        <div className="grid gap-5">
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <div role="timer" aria-label="Tiempo restante de respuesta" className="flex w-full items-center gap-3 cursor-help">
                  <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-muted">
                    <div
                      className={`h-full transition-all duration-200 ${isLowTime ? "bg-red-500" : "bg-primary"}`}
                      style={{ width: `${timePercent}%` }}
                    />
                  </div>
                  <span className={`min-w-[3.25rem] text-right font-mono text-sm font-bold tabular-nums ${isLowTime ? "text-red-500" : "text-foreground"}`}>
                    {remaining}s
                  </span>
                </div>
              </TooltipTrigger>
              <TooltipContent side="bottom">
                Tiempo disponible para responder esta pregunta
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>

          <Card>
            <CardHeader>
              <CardTitle>Pregunta {state.position} de {state.question_count}</CardTitle>
              <Progress value={state.answered_count / state.question_count * 100} aria-label="Progreso del examen" />
            </CardHeader>
            <CardContent className="grid gap-4">
              <p className="text-lg">{state.current_question.prompt}</p>
              {state.current_question.choices.map(choice => <p key={choice.code}>{choice.code}: {choice.text}</p>)}
              <div className="flex flex-wrap gap-3">
                <Button disabled={busy || recording || retryReady || remaining <= 0} onClick={record}>Grabar respuesta</Button>
                <Button disabled={busy || (!recording && !retryReady)} onClick={send}>{retryReady ? "Reenviar misma respuesta" : "Terminar y enviar respuesta"}</Button>
                {recording && <Button variant="outline" disabled={busy} onClick={() => { captureAbort.current?.abort(); capture.current = null; setRecording(false) }}>Cancelar grabación</Button>}
              </div>
              {recording && <p role="status" className="text-sm font-medium text-primary">Micrófono grabando. Terminá y enviá tu respuesta antes de que se acabe el tiempo.</p>}
            </CardContent>
          </Card>
        </div>
      )}

      {state && !state.current_question && state.status !== "CANCELLED" && (
        <Card>
          <CardContent className="py-8 text-center text-sm text-muted-foreground">
            Pasando a la siguiente fase de pruebas…
          </CardContent>
        </Card>
      )}
    </main>
  )
}

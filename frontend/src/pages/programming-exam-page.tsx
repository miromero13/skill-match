import { useEffect, useRef, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { PythonCodeEditor } from "@/components/programming/python-code-editor"
import { startOralRecording, type OralRecording } from "@/services/oral-recording"
import { getEvaluationChallenge, runChallenge, submitChallengeSolution, submitCodeDefense } from "@/services/programming-service"
import { theoryExam } from "@/services/theory-exam-service"
import { ApiError } from "@/types/api"
import type { Challenge, ChallengeRunResult } from "@/types/programming"

const DEFENSE_SECONDS = 90
const messageOf = (error: unknown) => error instanceof Error ? error.message : "No se pudo completar la operación."

export function ProgrammingExamPage() {
  const { id = "" } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [challenge, setChallenge] = useState<Challenge | null>(null)
  const [code, setCode] = useState("")
  const [result, setResult] = useState<ChallengeRunResult | null>(null)
  const [hasTested, setHasTested] = useState(false)
  const [notice, setNotice] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  // Oral defense state
  const [recording, setRecording] = useState(false)
  const [retryReady, setRetryReady] = useState(false)
  const [defenseRemaining, setDefenseRemaining] = useState(DEFENSE_SECONDS)
  const alive = useRef(true)
  const capture = useRef<OralRecording | null>(null)
  const captureAbort = useRef<AbortController | null>(null)
  const pendingDefense = useRef<{ submission_id: string; audio_base64: string } | null>(null)

  useEffect(() => {
    alive.current = true
    if (!id) return
    void getEvaluationChallenge(id).then((item) => {
      if (!alive.current) return
      setChallenge(item)
      setCode(item.starter_code)
    })
    return () => {
      alive.current = false
      captureAbort.current?.abort()
      capture.current?.cancel()
      capture.current = null
      pendingDefense.current = null
    }
  }, [id])

  useEffect(() => {
    if (!submitted) return
    setDefenseRemaining(DEFENSE_SECONDS)
    const timer = setInterval(() => {
      setDefenseRemaining((prev) => (prev > 0 ? prev - 1 : 0))
    }, 1000)
    return () => clearInterval(timer)
  }, [submitted])

  const run = async () => {
    if (!challenge || !code.trim()) return
    setBusy(true)
    setNotice("")
    setError("")
    try {
      setResult(await runChallenge(challenge.id, code))
      setHasTested(true)
    } catch (reason) {
      if (alive.current) setError(messageOf(reason))
    } finally {
      if (alive.current) setBusy(false)
    }
  }

  const submit = async () => {
    if (!id || !challenge || !code.trim() || !hasTested) return
    setBusy(true)
    setNotice("")
    setError("")
    try {
      const response = await submitChallengeSolution(id, challenge.id, code)
      setResult(response)
      setSubmitted(true)
      setNotice("Código entregado. Ahora explicá brevemente por qué lo resolviste así.")
    } catch (reason) {
      if (alive.current) setError(messageOf(reason))
    } finally {
      if (alive.current) setBusy(false)
    }
  }

  const startDefenseRecording = async () => {
    if (busy || recording || pendingDefense.current) return
    setBusy(true)
    setError("")
    try {
      const controller = new AbortController()
      captureAbort.current = controller
      const acquired = await startOralRecording(controller.signal, (text) => {
        if (alive.current) {
          setRecording(false)
          setError(text)
          capture.current = null
        }
      })
      if (!alive.current || controller.signal.aborted) {
        acquired.cancel()
        return
      }
      capture.current = acquired
      setRecording(true)
    } catch (reason) {
      if (alive.current) setError(messageOf(reason))
    } finally {
      if (alive.current) setBusy(false)
    }
  }

  const sendDefense = async () => {
    if (busy) return
    setBusy(true)
    setError("")
    try {
      if (!pendingDefense.current && capture.current) {
        const current = capture.current
        capture.current = null
        setRecording(false)
        pendingDefense.current = {
          submission_id: crypto.randomUUID(),
          audio_base64: await current.stop(),
        }
        setRetryReady(true)
      }
      if (!pendingDefense.current) return
      await submitCodeDefense(id, pendingDefense.current)
      if (!alive.current) return
      pendingDefense.current = null
      setRetryReady(false)
      if (document.fullscreenElement) void document.exitFullscreen?.().catch(() => undefined)
      navigate(`/evaluation/${id}/result`, { replace: true })
    } catch (reason) {
      if (reason instanceof ApiError && [409, 410].includes(reason.statuscode)) {
        pendingDefense.current = null
        if (alive.current) setRetryReady(false)
      }
      if (alive.current) setError(messageOf(reason))
    } finally {
      if (alive.current) setBusy(false)
    }
  }

  const cancelEvaluation = async () => {
    if (busy) return
    setBusy(true)
    try {
      captureAbort.current?.abort()
      capture.current?.cancel()
      capture.current = null
      setRecording(false)
      await theoryExam.cancel(id)
      if (document.fullscreenElement) void document.exitFullscreen?.().catch(() => undefined)
      navigate("/app/teaching-skills", { replace: true })
    } finally {
      if (alive.current) setBusy(false)
    }
  }

  if (!challenge) {
    return (
      <div className="grid min-h-screen place-items-center bg-[#0F1416] p-6 text-[#F0FDFA]">
        <p>Cargando reto de programación...</p>
      </div>
    )
  }

  const progress = result ? (result.passed_tests / Math.max(result.total_tests, 1)) * 100 : 0
  const defensePercent = Math.max(0, Math.min(100, (defenseRemaining / DEFENSE_SECONDS) * 100))
  const defenseLow = defenseRemaining <= 15 || defensePercent <= 20

  return (
    <div className="min-h-screen bg-[#0F1416] p-4 text-[#F0FDFA] md:p-8">
      <div className="mx-auto max-w-7xl space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold">{submitted ? "Defensa oral del código" : "Reto práctico de programación"}</h1>
            <p className="text-xs text-[#8B9D9F]">
              {submitted
                ? "Explicá cómo resolviste el reto o qué dificultades encontraste."
                : "Probá tu código al menos una vez antes de entregarlo."}
            </p>
          </div>
          <Button variant="destructive" size="sm" disabled={busy} onClick={() => void cancelEvaluation()}>
            Cancelar evaluación
          </Button>
        </div>

        {error && (
          <Alert variant="destructive">
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {submitted ? (
          <Card className="border-[#1E2629] bg-[#141C1E] text-[#F0FDFA]">
            <CardHeader className="space-y-3">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div role="timer" aria-label="Tiempo restante de defensa oral" className="flex w-full items-center gap-3 cursor-help">
                      <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-[#1E2629]">
                        <div
                          className={`h-full transition-all duration-200 ${defenseLow ? "bg-red-500" : "bg-[#00786F]"}`}
                          style={{ width: `${defensePercent}%` }}
                        />
                      </div>
                      <span className={`min-w-[3.25rem] text-right font-mono text-sm font-bold tabular-nums ${defenseLow ? "text-red-500" : "text-[#F0FDFA]"}`}>
                        {defenseRemaining}s
                      </span>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent side="bottom">
                    Tiempo disponible para explicar tu solución
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <CardTitle>Explicá tu solución para: {challenge.title}</CardTitle>
                {result && (
                  <Badge variant={result.status === "PASSED" ? "default" : "outline"}>
                    Tests: {result.passed_tests}/{result.total_tests}
                  </Badge>
                )}
              </div>
              <CardDescription className="text-[#8B9D9F]">
                Contanos en voz alta por qué elegiste este enfoque, qué estructuras usaste o por qué no pudiste completarlo.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap gap-3">
                <Button disabled={busy || recording || retryReady} onClick={() => void startDefenseRecording()}>
                  Grabar explicación
                </Button>
                <Button disabled={busy || (!recording && !retryReady)} onClick={() => void sendDefense()}>
                  {retryReady ? "Reenviar explicación y finalizar" : "Enviar defensa y finalizar"}
                </Button>
                {recording && (
                  <Button
                    variant="outline"
                    disabled={busy}
                    onClick={() => {
                      captureAbort.current?.abort()
                      capture.current = null
                      setRecording(false)
                    }}
                  >
                    Cancelar grabación
                  </Button>
                )}
              </div>
              {recording && (
                <p role="status" className="text-sm font-medium text-[#2DD4BF]">
                  Micrófono grabando. Cuando termines, presioná «Enviar defensa y finalizar».
                </p>
              )}
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-6 lg:grid-cols-[minmax(320px,0.8fr)_minmax(0,1.2fr)]">
            <Card className="border-[#1E2629] bg-[#141C1E] text-[#F0FDFA]">
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <CardTitle>{challenge.title}</CardTitle>
                    <CardDescription className="mt-2 text-[#8B9D9F]">
                      Perfil Python 3.12 · Nivel {challenge.level_number} · tiempo máximo {challenge.time_limit_ms} ms
                    </CardDescription>
                  </div>
                  <Badge>{challenge.evaluation_modality}</Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-5">
                <div className="whitespace-pre-wrap text-sm leading-6 text-[#D5E4E3]">{challenge.statement}</div>
                <div>
                  <h2 className="mb-2 text-sm font-semibold">Ejemplos públicos</h2>
                  <div className="space-y-2">
                    {challenge.tests.map((test) => (
                      <div key={test.order_index} className="rounded-md border border-[#1E2629] p-3 text-xs">
                        <p className="font-semibold">{test.name}</p>
                        <p className="mt-2 text-[#8B9D9F]">Entrada: <code>{test.stdin_data || "(vacía)"}</code></p>
                        <p className="text-[#8B9D9F]">Salida: <code>{test.expected_stdout}</code></p>
                      </div>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="border-[#1E2629] bg-[#141C1E] text-[#F0FDFA]">
              <CardHeader>
                <CardTitle>Tu solución al reto</CardTitle>
                <CardDescription className="text-[#8B9D9F]">
                  Ejecutá las pruebas al menos una vez para habilitar la entrega y defensa oral.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <PythonCodeEditor
                  value={code}
                  disabled={submitted || busy}
                  onChange={setCode}
                  minHeightClass="min-h-[420px]"
                  aria-label="Editor de código Python"
                />
                <div className="flex flex-wrap items-center justify-end gap-2">
                  <Button variant="outline" disabled={busy || submitted} onClick={() => void run()}>
                    {busy ? "Ejecutando…" : "Ejecutar pruebas"}
                  </Button>
                  <Button disabled={busy || submitted || !hasTested} onClick={() => void submit()}>
                    Entregar solución
                  </Button>
                </div>
                {!hasTested && (
                  <p className="text-right text-xs text-amber-300">
                    Debés probar tu código al menos una vez antes de entregar y explicar tu solución.
                  </p>
                )}
                {notice && (
                  <Alert>
                    <AlertTitle>Estado</AlertTitle>
                    <AlertDescription>{notice}</AlertDescription>
                  </Alert>
                )}
                {result && (
                  <div className="space-y-3 rounded-md border border-[#1E2629] p-4">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold">Resultado: {result.status}</span>
                      <span className="text-sm text-[#8B9D9F]">{result.passed_tests}/{result.total_tests} tests</span>
                    </div>
                    <Progress value={progress} aria-label="Progreso de tests" />
                    {result.results.map((test) => (
                      <div key={test.name} className="rounded border border-[#1E2629] p-3 text-xs">
                        <p className="font-semibold">{test.passed ? "✓" : "✕"} {test.name}</p>
                        {test.stderr && <pre className="mt-2 whitespace-pre-wrap text-red-300">{test.stderr}</pre>}
                        {test.stdout && <pre className="mt-2 whitespace-pre-wrap text-[#8B9D9F]">{test.stdout}</pre>}
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  )
}

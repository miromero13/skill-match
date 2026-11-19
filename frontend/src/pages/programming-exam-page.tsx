import { useEffect, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Textarea } from "@/components/ui/textarea"
import { getEvaluationProgrammingChallenge, runProgrammingChallenge, submitProgrammingSolution } from "@/services/programming-service"
import type { ProgrammingChallenge, ProgrammingRunResult } from "@/types/programming"

export function ProgrammingExamPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [challenge, setChallenge] = useState<ProgrammingChallenge | null>(null)
  const [code, setCode] = useState("")
  const [result, setResult] = useState<ProgrammingRunResult | null>(null)
  const [notice, setNotice] = useState("")
  const [busy, setBusy] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  useEffect(() => {
    if (!id) return
    let alive = true
    void getEvaluationProgrammingChallenge(id).then((item) => {
      if (!alive) return
      setChallenge(item)
      setCode(item.starter_code)
    })
    return () => { alive = false }
  }, [id])

  const run = async () => {
    if (!challenge || !code.trim()) return
    setBusy(true)
    setNotice("")
    try {
      setResult(await runProgrammingChallenge(challenge.id, code))
    } finally {
      setBusy(false)
    }
  }

  const submit = async () => {
    if (!id || !challenge || !code.trim()) return
    setBusy(true)
    setNotice("")
    try {
      const response = await submitProgrammingSolution(id, challenge.id, code)
      setResult(response)
      setSubmitted(true)
      setNotice("La solución quedó registrada. No se puede editar esta entrega.")
    } finally {
      setBusy(false)
    }
  }

  if (!challenge) {
    return <div className="grid min-h-screen place-items-center bg-[#0F1416] p-6 text-[#F0FDFA]"><p>Cargando reto de programación...</p></div>
  }

  const progress = result ? (result.passed_tests / Math.max(result.total_tests, 1)) * 100 : 0
  return (
    <div className="min-h-screen bg-[#0F1416] p-4 text-[#F0FDFA] md:p-8">
      <div className="mx-auto grid max-w-7xl gap-6 lg:grid-cols-[minmax(320px,0.8fr)_minmax(0,1.2fr)]">
        <Card className="border-[#1E2629] bg-[#141C1E] text-[#F0FDFA]"><CardHeader><div className="flex items-start justify-between gap-3"><div><CardTitle>{challenge.title}</CardTitle><CardDescription className="mt-2 text-[#8B9D9F]">Python · Nivel {challenge.level_number} · tiempo máximo {challenge.time_limit_ms} ms</CardDescription></div><Badge>SM-40</Badge></div></CardHeader><CardContent className="space-y-5"><div className="whitespace-pre-wrap text-sm leading-6 text-[#D5E4E3]">{challenge.statement}</div><div><h2 className="mb-2 text-sm font-semibold">Ejemplos públicos</h2><div className="space-y-2">{challenge.tests.map((test) => <div key={test.order_index} className="rounded-md border border-[#1E2629] p-3 text-xs"><p className="font-semibold">{test.name}</p><p className="mt-2 text-[#8B9D9F]">Entrada: <code>{test.stdin_data || "(vacía)"}</code></p><p className="text-[#8B9D9F]">Salida: <code>{test.expected_stdout}</code></p></div>)}</div></div><p className="text-xs text-[#8B9D9F]">Tu código se ejecuta en un contenedor aislado. No se envían audio, video ni código a un proveedor de IA.</p></CardContent></Card>
        <Card className="border-[#1E2629] bg-[#141C1E] text-[#F0FDFA]"><CardHeader><CardTitle>Tu solución</CardTitle><CardDescription className="text-[#8B9D9F]">Probá con tests públicos antes de entregar.</CardDescription></CardHeader><CardContent className="space-y-4"><Textarea value={code} disabled={submitted || busy} onChange={(event) => setCode(event.target.value)} className="min-h-[420px] font-mono text-sm" aria-label="Editor de código Python" /><div className="flex flex-wrap justify-end gap-2"><Button variant="outline" disabled={busy || submitted} onClick={() => void run()}>Ejecutar pruebas</Button><Button disabled={busy || submitted} onClick={() => void submit()}>Entregar solución</Button></div>{notice && <Alert><AlertTitle>Estado</AlertTitle><AlertDescription>{notice}</AlertDescription></Alert>}{result && <div className="space-y-3 rounded-md border border-[#1E2629] p-4"><div className="flex items-center justify-between"><span className="font-semibold">Resultado: {result.status}</span><span className="text-sm text-[#8B9D9F]">{result.passed_tests}/{result.total_tests} tests</span></div><Progress value={progress} aria-label="Progreso de tests" />{result.results.map((test) => <div key={test.name} className="rounded border border-[#1E2629] p-3 text-xs"><p className="font-semibold">{test.passed ? "✓" : "✕"} {test.name}</p>{test.stderr && <pre className="mt-2 whitespace-pre-wrap text-red-300">{test.stderr}</pre>}{test.stdout && <pre className="mt-2 whitespace-pre-wrap text-[#8B9D9F]">{test.stdout}</pre>}</div>)}</div>}{submitted && <Button variant="ghost" onClick={() => navigate("/app")}>Volver a la plataforma</Button>}</CardContent></Card>
      </div>
    </div>
  )
}

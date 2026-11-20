import { useCallback, useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { CheckCircle2, Award, AlertCircle, RotateCcw } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { theoryExam, type FinalEvaluationResult } from "@/services/theory-exam-service"

const messageOf = (error: unknown) => error instanceof Error ? error.message : "No se pudo finalizar la evaluación."

export function EvaluationResultPage() {
  const { id = "" } = useParams<{ id: string }>()
  const [result, setResult] = useState<FinalEvaluationResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  const finalize = useCallback(async () => {
    if (!id) return
    setLoading(true)
    setError("")
    try {
      const response = await theoryExam.finalize(id)
      setResult(response.data)
    } catch (reason) {
      setError(messageOf(reason))
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    void finalize()
  }, [finalize])

  return (
    <main className="min-h-screen bg-[#0F1416] p-4 text-[#F0FDFA] md:p-8">
      <div className="mx-auto max-w-4xl space-y-6">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-extrabold">Resultado final de la evaluación</h1>
            <p className="text-sm text-[#8B9D9F]">Calificación integral generada al concluir todas las etapas.</p>
          </div>
          {result && (
            <Badge
              variant={result.passed ? "default" : "destructive"}
              className={result.passed ? "bg-emerald-600 text-white px-3 py-1 text-sm" : "px-3 py-1 text-sm"}
            >
              {result.passed ? "VALIDADO" : "NO APROBADO"}
            </Badge>
          )}
        </header>

        {loading && (
          <Card className="border-[#1E2629] bg-[#141C1E] text-[#F0FDFA]">
            <CardContent className="py-12 text-center space-y-2">
              <p className="text-base font-medium">Evaluando tus respuestas con IA…</p>
              <p className="text-xs text-[#8B9D9F]">Esto puede tardar unos segundos mientras se corrigen tus explicaciones.</p>
            </CardContent>
          </Card>
        )}

        {error && !loading && (
          <Card className="border-destructive/40 bg-[#141C1E] text-[#F0FDFA]">
            <CardContent className="flex flex-wrap items-center justify-between gap-4 py-6">
              <div className="flex items-center gap-3 text-red-300">
                <AlertCircle className="h-5 w-5 shrink-0" />
                <p className="text-sm">{error}</p>
              </div>
              <Button variant="outline" onClick={() => void finalize()}>
                <RotateCcw className="mr-2 h-4 w-4" />
                Reintentar calificación
              </Button>
            </CardContent>
          </Card>
        )}

        {result && !loading && (
          <>
            <Card className="border-[#1E2629] bg-[#141C1E] text-[#F0FDFA]">
              <CardHeader>
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    {result.passed ? (
                      <Award className="h-8 w-8 text-emerald-400" />
                    ) : (
                      <AlertCircle className="h-8 w-8 text-red-400" />
                    )}
                    <div>
                      <CardTitle className="text-xl">
                        Nota final: {result.final_score.toFixed(1)} / 100
                      </CardTitle>
                      <CardDescription className="text-[#8B9D9F]">
                        {result.passed
                          ? "¡Felicitaciones! Superaste el umbral de aprobación (70 puntos)."
                          : "No alcanzaste el mínimo de 70 puntos para validar la habilidad."}
                      </CardDescription>
                    </div>
                  </div>
                </div>
                <Progress value={result.final_score} className="mt-3" aria-label="Nota final" />
              </CardHeader>
              {result.skill_validated && (
                <CardContent>
                  <div className="flex items-center gap-2.5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-300">
                    <CheckCircle2 className="h-4 w-4 shrink-0" />
                    <span>Tu habilidad quedó marcada como <strong>VERIFICADA</strong> en tu perfil y pasaporte de habilidades.</span>
                  </div>
                </CardContent>
              )}
            </Card>

            <div className="grid gap-4 md:grid-cols-2">
              <Card className="border-[#1E2629] bg-[#141C1E] text-[#F0FDFA]">
                <CardHeader>
                  <CardTitle className="text-base">Evaluación teórica</CardTitle>
                  <CardDescription className="text-[#8B9D9F]">
                    Puntaje: {result.theory_score} / {result.theory_max_score}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-xs">
                  {result.theory_feedback?.map((item, idx) => (
                    <div key={item.question_id ?? idx} className="rounded border border-[#1E2629] p-3 space-y-1">
                      <p className="font-semibold text-[#F0FDFA]">
                        Pregunta {idx + 1} · {item.points}/{item.max_score} pts
                      </p>
                      <p className="text-[#8B9D9F]">{item.feedback}</p>
                    </div>
                  ))}
                </CardContent>
              </Card>

              {result.has_coding_stage && (
                <Card className="border-[#1E2629] bg-[#141C1E] text-[#F0FDFA]">
                  <CardHeader>
                    <CardTitle className="text-base">Reto Sandbox y Defensa Oral</CardTitle>
                    <CardDescription className="text-[#8B9D9F]">
                      Tests: {result.sandbox_passed_tests ?? 0}/{result.sandbox_total_tests ?? 0} · Defensa: {result.defense_score ?? 0}/100
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3 text-xs">
                    {result.defense_feedback && (
                      <div className="rounded border border-[#1E2629] p-3 space-y-1">
                        <p className="font-semibold text-[#F0FDFA]">Feedback de tu explicación</p>
                        <p className="text-[#8B9D9F]">{result.defense_feedback}</p>
                      </div>
                    )}
                    {result.defense_transcript && (
                      <div className="rounded border border-[#1E2629] p-3 space-y-1">
                        <p className="font-semibold text-[#F0FDFA]">Transcripción registrada</p>
                        <p className="italic text-[#8B9D9F]">"{result.defense_transcript}"</p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}
            </div>

            <div className="flex flex-wrap justify-end gap-3">
              <Button asChild variant="outline">
                <Link to="/app/teaching-skills">Ir a Mis Habilidades</Link>
              </Button>
              <Button asChild>
                <Link to="/app/profile">Ver mi Perfil / Pasaporte</Link>
              </Button>
            </div>
          </>
        )}
      </div>
    </main>
  )
}

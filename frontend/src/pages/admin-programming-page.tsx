import { useEffect, useState } from "react"
import { Plus, Trash2 } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { getSkills } from "@/services/admin-catalog-service"
import { createChallenge, listChallenges, previewChallenge, publishChallenge } from "@/services/programming-service"
import type { Skill } from "@/types/catalog"
import type { Challenge, ChallengePayload, ChallengeRunResult, ChallengeTestCase, EvaluationModality } from "@/types/programming"

const PROGRAMMING_LEVELS = [
  { value: "1", label: "Nivel 1 · Principiante" },
  { value: "2", label: "Nivel 2 · Elemental" },
  { value: "3", label: "Nivel 3 · Intermedio" },
  { value: "4", label: "Nivel 4 · Avanzado" },
  { value: "5", label: "Nivel 5 · Master Pedagogo" },
] as const

const emptyTest = (orderIndex: number): ChallengeTestCase => ({
  name: `Caso ${orderIndex + 1}`,
  stdin_data: "",
  expected_stdout: "",
  visibility: orderIndex === 0 ? "PUBLIC" : "HIDDEN",
  order_index: orderIndex,
})

export function AdminProgrammingPage() {
  const [skills, setSkills] = useState<Skill[]>([])
  const [challenges, setChallenges] = useState<Challenge[]>([])
  const [selectedSkill, setSelectedSkill] = useState("")
  const [level, setLevel] = useState("1")
  const [modality, setModality] = useState<EvaluationModality>("SANDBOX")
  const [executionProfile, setExecutionProfile] = useState("PYTHON_3_12")
  const [title, setTitle] = useState("")
  const [statement, setStatement] = useState("")
  const [starterCode, setStarterCode] = useState("def solve():\n    pass\n\nif __name__ == \"__main__\":\n    solve()")
  const [tests, setTests] = useState<ChallengeTestCase[]>([emptyTest(0), emptyTest(1)])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testCode, setTestCode] = useState(starterCode)
  const [testResult, setTestResult] = useState<ChallengeRunResult | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const skillResponse = await getSkills(undefined, "")
      const availableSkills = skillResponse.items
      setSkills(availableSkills)
      if (!selectedSkill && availableSkills[0]) setSelectedSkill(availableSkills[0].id)
      setChallenges(await listChallenges())
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [])

  const updateTest = (index: number, patch: Partial<ChallengeTestCase>) => {
    setTests((current) => current.map((test, testIndex) => testIndex === index ? { ...test, ...patch } : test))
  }

  const addTest = () => setTests((current) => [...current, emptyTest(current.length)])
  const removeTest = (index: number) => setTests((current) => current.length > 1 ? current.filter((_, testIndex) => testIndex !== index).map((test, testIndex) => ({ ...test, order_index: testIndex })) : current)

  const buildPayload = (): ChallengePayload => ({
      skill_id: selectedSkill,
      level_number: Number(level),
      title: title.trim(),
      statement: statement.trim(),
      evaluation_modality: modality,
      execution_profile: executionProfile,
      starter_code: starterCode,
      time_limit_ms: 2000,
      memory_limit_mb: 128,
      max_output_bytes: 65536,
      allowed_imports: [],
      blocked_imports: [],
      tests: tests.map((test, index) => ({ ...test, order_index: index })),
    })

  const canTest = Boolean(selectedSkill && title.trim() && statement.trim() && testCode.trim() && tests.every((test) => test.name.trim() && test.expected_stdout.trim()))

  const testDraft = async () => {
    if (!canTest) return
    setTesting(true)
    try {
      setTestResult(await previewChallenge(buildPayload(), testCode))
    } finally {
      setTesting(false)
    }
  }

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!canTest) return
    const payload = buildPayload()
    setSaving(true)
    try {
      await createChallenge(payload)
      setTitle("")
      setStatement("")
      setTests([emptyTest(0), emptyTest(1)])
      await load()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 md:p-8">
      <div>
        <h1 className="text-2xl font-extrabold text-[#F0FDFA]">Retos</h1>
        <p className="mt-1 text-sm text-[#8B9D9F]">Definí qué reto verá el miembro después de teoría.</p>
      </div>
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.9fr)]">
        <Card className="border-[#1E2629] bg-[#141C1E] text-[#F0FDFA]">
          <CardHeader><CardTitle>Nuevo reto evaluable</CardTitle><CardDescription className="text-[#8B9D9F]">Las pruebas ocultas nunca se muestran al miembro.</CardDescription></CardHeader>
          <CardContent>
            <form onSubmit={submit} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2"><Label htmlFor="programming-skill">Habilidad</Label><Select value={selectedSkill} onValueChange={setSelectedSkill}><SelectTrigger id="programming-skill"><SelectValue placeholder="Seleccioná una habilidad" /></SelectTrigger><SelectContent>{skills.map((skill) => <SelectItem key={skill.id} value={skill.id}>{skill.name}</SelectItem>)}</SelectContent></Select></div>
                <div className="space-y-2"><Label htmlFor="programming-level">Nivel</Label><Select value={level} onValueChange={setLevel}><SelectTrigger id="programming-level"><SelectValue placeholder="Seleccioná un nivel" /></SelectTrigger><SelectContent>{PROGRAMMING_LEVELS.map((item) => <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>)}</SelectContent></Select></div>
              </div>
              <div className="grid gap-4 sm:grid-cols-2"><div className="space-y-2"><Label htmlFor="challenge-modality">Modalidad</Label><Select value={modality} onValueChange={(value: EvaluationModality) => setModality(value)}><SelectTrigger id="challenge-modality"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="SANDBOX">Sandbox</SelectItem><SelectItem value="SPREADSHEET" disabled>Planilla / Excel (próximamente)</SelectItem></SelectContent></Select></div><div className="space-y-2"><Label htmlFor="challenge-profile">Perfil de ejecución</Label><Select value={executionProfile} onValueChange={setExecutionProfile}><SelectTrigger id="challenge-profile"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="PYTHON_3_12">Python 3.12</SelectItem></SelectContent></Select></div></div>
              <div className="space-y-2"><Label htmlFor="challenge-title">Título</Label><Input id="challenge-title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Suma de dos números" /></div>
              <div className="space-y-2"><Label htmlFor="programming-statement">Consigna</Label><Textarea id="challenge-statement" value={statement} onChange={(event) => setStatement(event.target.value)} rows={6} placeholder="Explicá qué debe resolver el miembro..." /></div>
              <div className="space-y-2"><Label htmlFor="programming-starter">Código inicial</Label><Textarea id="challenge-starter" value={starterCode} onChange={(event) => { setStarterCode(event.target.value); if (!testCode.trim()) setTestCode(event.target.value) }} rows={7} className="font-mono text-xs" /></div>
              <div className="space-y-2 rounded-md border border-[#1E2629] p-3"><div><Label htmlFor="challenge-test-code">Código para probar</Label><p className="text-xs text-[#8B9D9F]">Ejecuta todos los casos sin guardar ni publicar el reto.</p></div><Textarea id="challenge-test-code" value={testCode} onChange={(event) => setTestCode(event.target.value)} rows={8} className="font-mono text-xs" /><Button type="button" variant="secondary" onClick={testDraft} disabled={testing || !canTest}>{testing ? "Probando..." : "Probar reto"}</Button>{testResult && <div className="space-y-1 text-sm"><Badge variant={testResult.status === "PASSED" ? "default" : "destructive"}>{testResult.status} · {testResult.passed_tests}/{testResult.total_tests}</Badge>{testResult.results.map((result) => <p key={result.name} className={result.passed ? "text-emerald-300" : "text-red-300"}>{result.name}: {result.passed ? "correcto" : "falló"}</p>)}</div>}</div>
              <div className="space-y-3"><div className="flex items-center justify-between"><Label>Tests</Label><Button type="button" variant="outline" size="sm" onClick={addTest}><Plus className="mr-1 h-4 w-4" />Agregar caso</Button></div>{tests.map((test, index) => <div key={index} className="space-y-2 rounded-md border border-[#1E2629] p-3"><div className="flex items-center justify-between gap-2"><Input value={test.name} onChange={(event) => updateTest(index, { name: event.target.value })} aria-label={`Nombre del test ${index + 1}`} /><div className="flex items-center gap-2"><Select value={test.visibility} onValueChange={(value: "PUBLIC" | "HIDDEN") => updateTest(index, { visibility: value })}><SelectTrigger className="w-32"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="PUBLIC">Público</SelectItem><SelectItem value="HIDDEN">Oculto</SelectItem></SelectContent></Select><Button type="button" variant="ghost" size="icon" disabled={tests.length === 1} onClick={() => removeTest(index)} aria-label={`Eliminar test ${index + 1}`}><Trash2 className="h-4 w-4" /></Button></div></div><Textarea value={test.stdin_data} onChange={(event) => updateTest(index, { stdin_data: event.target.value })} placeholder="Entrada stdin" aria-label={`Entrada del test ${index + 1}`} /><Textarea value={test.expected_stdout} onChange={(event) => updateTest(index, { expected_stdout: event.target.value })} placeholder="Salida esperada" aria-label={`Salida del test ${index + 1}`} /></div>)}</div>
              <div className="flex justify-end"><Button type="submit" disabled={saving || loading || !selectedSkill}>{saving ? "Guardando..." : "Guardar borrador"}</Button></div>
            </form>
          </CardContent>
        </Card>
        <Card className="border-[#1E2629] bg-[#141C1E] text-[#F0FDFA]"><CardHeader><CardTitle>Versiones creadas</CardTitle><CardDescription className="text-[#8B9D9F]">Publicá solo cuando haya tests públicos y ocultos.</CardDescription></CardHeader><CardContent className="space-y-3">{challenges.length === 0 ? <p className="text-sm text-[#8B9D9F]">Todavía no hay retos.</p> : challenges.map((challenge) => <div key={challenge.id} className="rounded-md border border-[#1E2629] p-3"><div className="flex items-start justify-between gap-2"><div><p className="font-semibold">{challenge.title}</p><p className="text-xs text-[#8B9D9F]">Nivel {challenge.level_number} · v{challenge.version}</p></div><Badge variant={challenge.status === "PUBLISHED" ? "default" : "outline"}>{challenge.status}</Badge></div>{challenge.status === "DRAFT" && <Button className="mt-3" size="sm" onClick={() => publishChallenge(challenge.id).then(load)}>Publicar versión</Button>}</div>)}</CardContent></Card>
      </div>
    </div>
  )
}

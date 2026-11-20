import { useEffect, useState } from "react"
import { Plus, Sparkles, Trash2 } from "lucide-react"
import { PYTHON_CHALLENGES_SEED } from "@/data/python-challenges-seed"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { PythonCodeEditor } from "@/components/programming/python-code-editor"
import { getSkills } from "@/services/admin-catalog-service"
import {
  archiveChallenge,
  createChallenge,
  getAdminChallenge,
  getChallengeDetail,
  listChallenges,
  publishChallenge,
  runChallenge,
  updateChallenge,
} from "@/services/programming-service"
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
  const [editingId, setEditingId] = useState<string | null>(null)
  const [seeding, setSeeding] = useState(false)
  const [seedMessage, setSeedMessage] = useState("")
  const [simId, setSimId] = useState("")
  const [simChallenge, setSimChallenge] = useState<Challenge | null>(null)
  const [simCode, setSimCode] = useState("")
  const [simBusy, setSimBusy] = useState(false)
  const [simResult, setSimResult] = useState<ChallengeRunResult | null>(null)

  const selectSimChallenge = async (id: string) => {
    setSimId(id)
    setSimResult(null)
    if (!id) {
      setSimChallenge(null)
      setSimCode("")
      return
    }
    const detail = await getChallengeDetail(id)
    setSimChallenge(detail)
    setSimCode(detail.starter_code || "")
  }

  const load = async () => {
    setLoading(true)
    try {
      const skillResponse = await getSkills(undefined, "")
      const availableSkills = skillResponse.items
      setSkills(availableSkills)
      if (!selectedSkill && availableSkills[0]) setSelectedSkill(availableSkills[0].id)
      const loadedChallenges = await listChallenges()
      setChallenges(loadedChallenges)
      const firstPublished = loadedChallenges.find((item) => item.status === "PUBLISHED")
      if (!simId && firstPublished) {
        await selectSimChallenge(firstPublished.id)
      }
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

  const canSave = Boolean(selectedSkill && title.trim() && statement.trim() && tests.every((test) => test.name.trim() && test.expected_stdout.trim()))

  const resetForm = () => {
    setEditingId(null)
    setTitle("")
    setStatement("")
    setStarterCode("def solve():\n    pass\n\nif __name__ == \"__main__\":\n    solve()")
    setTests([emptyTest(0), emptyTest(1)])
  }

  const startEdit = async (id: string) => {
    const detail = await getAdminChallenge(id)
    setEditingId(detail.id)
    setSelectedSkill(detail.skill_id)
    setLevel(String(detail.level_number))
    setModality(detail.evaluation_modality)
    setExecutionProfile(detail.execution_profile)
    setTitle(detail.title)
    setStatement(detail.statement)
    setStarterCode(detail.starter_code)
    setTests(detail.tests.length > 0 ? detail.tests : [emptyTest(0), emptyTest(1)])
  }

  const publishAllPending = async () => {
    const pending = challenges.filter((c) => c.status !== "PUBLISHED")
    if (pending.length === 0) return
    setSeeding(true)
    try {
      for (const item of pending) {
        await publishChallenge(item.id, { silent: true })
      }
      setSeedMessage(`Se publicaron ${pending.length} retos pendientes.`)
      await load()
    } finally {
      setSeeding(false)
    }
  }

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!canSave) return
    const payload = buildPayload()
    setSaving(true)
    try {
      if (editingId) {
        await updateChallenge(editingId, payload)
      } else {
        await createChallenge(payload)
      }
      resetForm()
      await load()
    } finally {
      setSaving(false)
    }
  }

  const seedPythonChallenges = async () => {
    if (!selectedSkill || seeding) return
    setSeeding(true)
    setSeedMessage("")
    try {
      for (const template of PYTHON_CHALLENGES_SEED) {
        const created = await createChallenge(
          {
            ...template,
            skill_id: selectedSkill,
            level_number: Number(level),
            evaluation_modality: modality,
            execution_profile: executionProfile,
          },
          { silent: true }
        )
        await publishChallenge(created.id, { silent: true })
      }
      setSeedMessage(`Se crearon y publicaron ${PYTHON_CHALLENGES_SEED.length} retos (${modality} · ${executionProfile} · Nivel ${level}).`)
      await load()
    } finally {
      setSeeding(false)
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 md:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-[#F0FDFA]">Retos</h1>
          <p className="mt-1 text-sm text-[#8B9D9F]">Definí qué reto verá el miembro después de teoría.</p>
        </div>
        <Button
          type="button"
          variant="outline"
          disabled={!selectedSkill || seeding || saving}
          onClick={() => void seedPythonChallenges()}
          className="border-[#1E2629] bg-[#141C1E] hover:bg-[#1A2225] text-[#2DD4BF] font-semibold flex items-center gap-1.5 cursor-pointer"
        >
          <Sparkles className="h-4 w-4" />
          <span>{seeding ? "Creando 20 retos…" : "python-nivel1"}</span>
        </Button>
      </div>
      {seedMessage && (
        <p role="status" className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-4 py-2.5 text-sm text-emerald-300">
          {seedMessage}
        </p>
      )}
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
              <div className="space-y-2"><Label htmlFor="programming-starter">Código inicial</Label><Textarea id="challenge-starter" value={starterCode} onChange={(event) => setStarterCode(event.target.value)} rows={7} className="font-mono text-xs" /></div>
              <div className="space-y-3"><div className="flex items-center justify-between"><Label>Tests</Label><Button type="button" variant="outline" size="sm" onClick={addTest}><Plus className="mr-1 h-4 w-4" />Agregar caso</Button></div>{tests.map((test, index) => <div key={index} className="space-y-2 rounded-md border border-[#1E2629] p-3"><div className="flex items-center justify-between gap-2"><Input value={test.name} onChange={(event) => updateTest(index, { name: event.target.value })} aria-label={`Nombre del test ${index + 1}`} /><div className="flex items-center gap-2"><Select value={test.visibility} onValueChange={(value: "PUBLIC" | "HIDDEN") => updateTest(index, { visibility: value })}><SelectTrigger className="w-32"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="PUBLIC">Público</SelectItem><SelectItem value="HIDDEN">Oculto</SelectItem></SelectContent></Select><Button type="button" variant="ghost" size="icon" disabled={tests.length === 1} onClick={() => removeTest(index)} aria-label={`Eliminar test ${index + 1}`}><Trash2 className="h-4 w-4" /></Button></div></div><Textarea value={test.stdin_data} onChange={(event) => updateTest(index, { stdin_data: event.target.value })} placeholder="Entrada stdin" aria-label={`Entrada del test ${index + 1}`} /><Textarea value={test.expected_stdout} onChange={(event) => updateTest(index, { expected_stdout: event.target.value })} placeholder="Salida esperada" aria-label={`Salida del test ${index + 1}`} /></div>)}</div>
              <div className="flex justify-end gap-2">
                {editingId && (
                  <Button type="button" variant="outline" disabled={saving} onClick={resetForm}>
                    Cancelar edición
                  </Button>
                )}
                <Button type="submit" disabled={saving || loading || !canSave}>
                  {saving ? "Guardando..." : editingId ? "Guardar cambios" : "Guardar borrador"}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
        <Card className="border-[#1E2629] bg-[#141C1E] text-[#F0FDFA]">
          <CardHeader>
            <div className="flex items-center justify-between gap-2">
              <div>
                <CardTitle>Versiones creadas</CardTitle>
                <CardDescription className="text-[#8B9D9F]">Podés editar, publicar o archivar cada reto.</CardDescription>
              </div>
              {challenges.some((c) => c.status !== "PUBLISHED") && (
                <Button size="sm" variant="outline" disabled={seeding} onClick={() => void publishAllPending()}>
                  Publicar todos
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-3 max-h-[720px] overflow-y-auto">
            {challenges.length === 0 ? (
              <p className="text-sm text-[#8B9D9F]">Todavía no hay retos.</p>
            ) : (
              challenges.map((challenge) => (
                <div key={challenge.id} className="rounded-md border border-[#1E2629] p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-semibold">{challenge.title}</p>
                      <p className="text-xs text-[#8B9D9F]">Nivel {challenge.level_number} · v{challenge.version}</p>
                    </div>
                    <Badge variant={challenge.status === "PUBLISHED" ? "default" : "outline"}>{challenge.status}</Badge>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button size="sm" variant="outline" onClick={() => void startEdit(challenge.id)}>
                      Editar
                    </Button>
                    {challenge.status !== "PUBLISHED" ? (
                      <Button size="sm" onClick={() => void publishChallenge(challenge.id).then(load)}>
                        Publicar
                      </Button>
                    ) : (
                      <Button size="sm" variant="ghost" onClick={() => void archiveChallenge(challenge.id).then(load)}>
                        Archivar
                      </Button>
                    )}
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="border-[#1E2629] bg-[#141C1E] text-[#F0FDFA]">
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle>Simulador de examen (vista miembro)</CardTitle>
              <CardDescription className="text-[#8B9D9F]">
                Probá cualquier reto publicado exactamente como lo ve el postulante en el sandbox Docker.
              </CardDescription>
            </div>
            {challenges.some((c) => c.status === "PUBLISHED") && (
              <div className="w-full sm:w-72">
                <Select
                  value={simId}
                  onValueChange={(value) => { void selectSimChallenge(value) }}
                >
                  <SelectTrigger aria-label="Reto para simular">
                    <SelectValue placeholder="Elegí un reto publicado" />
                  </SelectTrigger>
                  <SelectContent>
                    {challenges
                      .filter((c) => c.status === "PUBLISHED")
                      .map((c) => (
                        <SelectItem key={c.id} value={c.id}>
                          {c.title} (Nivel {c.level_number})
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {(() => {
            if (!simChallenge) {
              return (
                <p className="text-sm text-[#8B9D9F]">
                  Publicá al menos un reto (o usá el botón <strong>python-retos-20</strong>) para probarlo aquí como en el examen.
                </p>
              )
            }
            const publicTests = (simChallenge.tests ?? []).filter((t) => t.visibility === "PUBLIC")
            const simProgress = simResult ? (simResult.passed_tests / Math.max(simResult.total_tests, 1)) * 100 : 0
            return (
              <div className="grid gap-6 lg:grid-cols-[minmax(280px,0.8fr)_minmax(0,1.2fr)]">
                <div className="space-y-4 rounded-md border border-[#1E2629] p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h3 className="text-lg font-bold">{simChallenge.title}</h3>
                      <p className="text-xs text-[#8B9D9F]">
                        {simChallenge.execution_profile} · Nivel {simChallenge.level_number} · {simChallenge.time_limit_ms} ms
                      </p>
                    </div>
                    <Badge>{simChallenge.evaluation_modality}</Badge>
                  </div>
                  <p className="whitespace-pre-wrap text-sm leading-6 text-[#D5E4E3]">{simChallenge.statement}</p>
                  <div className="space-y-2">
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-[#8B9D9F]">Ejemplos públicos</h4>
                    {publicTests.map((test) => (
                      <div key={test.order_index} className="rounded border border-[#1E2629] p-2.5 text-xs">
                        <p className="font-semibold">{test.name}</p>
                        <p className="mt-1 text-[#8B9D9F]">Entrada: <code>{test.stdin_data || "(vacía)"}</code></p>
                        <p className="text-[#8B9D9F]">Salida: <code>{test.expected_stdout}</code></p>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="space-y-4">
                  <PythonCodeEditor
                    value={simCode}
                    disabled={simBusy}
                    onChange={setSimCode}
                    minHeightClass="min-h-[320px]"
                    aria-label="Editor de código del simulador"
                  />
                  <div className="flex justify-end gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      disabled={simBusy}
                      onClick={() => { setSimCode(simChallenge.starter_code); setSimResult(null) }}
                    >
                      Restablecer código
                    </Button>
                    <Button
                      type="button"
                      disabled={simBusy || !simCode.trim()}
                      onClick={async () => {
                        setSimBusy(true)
                        try {
                          setSimResult(await runChallenge(simChallenge.id, simCode))
                        } finally {
                          setSimBusy(false)
                        }
                      }}
                    >
                      {simBusy ? "Ejecutando en sandbox…" : "Ejecutar pruebas"}
                    </Button>
                  </div>
                  {simResult && (
                    <div className="space-y-3 rounded-md border border-[#1E2629] p-4">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold">Resultado: {simResult.status}</span>
                        <span className="text-sm text-[#8B9D9F]">{simResult.passed_tests}/{simResult.total_tests} tests públicos</span>
                      </div>
                      <Progress value={simProgress} aria-label="Progreso de tests en simulador" />
                      {simResult.results.map((test) => (
                        <div key={test.name} className="rounded border border-[#1E2629] p-3 text-xs">
                          <p className="font-semibold">{test.passed ? "✓" : "✕"} {test.name}</p>
                          {test.stderr && <pre className="mt-2 whitespace-pre-wrap text-red-300">{test.stderr}</pre>}
                          {test.stdout && <pre className="mt-2 whitespace-pre-wrap text-[#8B9D9F]">{test.stdout}</pre>}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )
          })()}
        </CardContent>
      </Card>
    </div>
  )
}

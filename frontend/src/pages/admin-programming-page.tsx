import { useEffect, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { getSkills } from "@/services/admin-catalog-service"
import { createProgrammingChallenge, listProgrammingChallenges, publishProgrammingChallenge } from "@/services/programming-service"
import type { Skill } from "@/types/catalog"
import type { ProgrammingChallenge, ProgrammingChallengePayload, ProgrammingTestCase } from "@/types/programming"

const emptyTest = (orderIndex: number): ProgrammingTestCase => ({
  name: `Caso ${orderIndex + 1}`,
  stdin_data: "",
  expected_stdout: "",
  visibility: orderIndex === 0 ? "PUBLIC" : "HIDDEN",
  order_index: orderIndex,
})

export function AdminProgrammingPage() {
  const [skills, setSkills] = useState<Skill[]>([])
  const [challenges, setChallenges] = useState<ProgrammingChallenge[]>([])
  const [selectedSkill, setSelectedSkill] = useState("")
  const [level, setLevel] = useState("1")
  const [title, setTitle] = useState("")
  const [statement, setStatement] = useState("")
  const [starterCode, setStarterCode] = useState("def solve():\n    pass\n\nif __name__ == \"__main__\":\n    solve()")
  const [tests, setTests] = useState<ProgrammingTestCase[]>([emptyTest(0), emptyTest(1)])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const skillResponse = await getSkills(undefined, "")
      const programmingSkills = skillResponse.items.filter((skill) => {
        const name = skill.name.toLowerCase()
        return name.includes("python") || name.includes("program") || name.includes("código") || name.includes("codigo")
      })
      setSkills(programmingSkills)
      if (!selectedSkill && programmingSkills[0]) setSelectedSkill(programmingSkills[0].id)
      setChallenges(await listProgrammingChallenges())
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [])

  const updateTest = (index: number, patch: Partial<ProgrammingTestCase>) => {
    setTests((current) => current.map((test, testIndex) => testIndex === index ? { ...test, ...patch } : test))
  }

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!selectedSkill || !title.trim() || !statement.trim() || tests.some((test) => !test.name.trim() || !test.expected_stdout.trim())) return
    const payload: ProgrammingChallengePayload = {
      skill_id: selectedSkill,
      level_number: Number(level),
      title: title.trim(),
      statement: statement.trim(),
      language: "python",
      starter_code: starterCode,
      time_limit_ms: 2000,
      memory_limit_mb: 128,
      max_output_bytes: 65536,
      allowed_imports: [],
      blocked_imports: [],
      tests: tests.map((test, index) => ({ ...test, order_index: index })),
    }
    setSaving(true)
    try {
      await createProgrammingChallenge(payload)
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
        <h1 className="text-2xl font-extrabold text-[#F0FDFA]">Retos de programación</h1>
        <p className="mt-1 text-sm text-[#8B9D9F]">Definí la consigna y los tests que el miembro resolverá después de teoría.</p>
      </div>
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.9fr)]">
        <Card className="border-[#1E2629] bg-[#141C1E] text-[#F0FDFA]">
          <CardHeader><CardTitle>Nuevo reto</CardTitle><CardDescription className="text-[#8B9D9F]">Las pruebas ocultas nunca se muestran al miembro.</CardDescription></CardHeader>
          <CardContent>
            <form onSubmit={submit} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2"><Label htmlFor="programming-skill">Habilidad</Label><Select value={selectedSkill} onValueChange={setSelectedSkill}><SelectTrigger id="programming-skill"><SelectValue placeholder="Seleccioná una habilidad" /></SelectTrigger><SelectContent>{skills.map((skill) => <SelectItem key={skill.id} value={skill.id}>{skill.name}</SelectItem>)}</SelectContent></Select></div>
                <div className="space-y-2"><Label htmlFor="programming-level">Nivel</Label><Input id="programming-level" type="number" min={1} max={20} value={level} onChange={(event) => setLevel(event.target.value)} /></div>
              </div>
              <div className="space-y-2"><Label htmlFor="programming-title">Título</Label><Input id="programming-title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Suma de dos números" /></div>
              <div className="space-y-2"><Label htmlFor="programming-statement">Consigna</Label><Textarea id="programming-statement" value={statement} onChange={(event) => setStatement(event.target.value)} rows={6} placeholder="Explicá qué debe resolver el miembro..." /></div>
              <div className="space-y-2"><Label htmlFor="programming-starter">Código inicial</Label><Textarea id="programming-starter" value={starterCode} onChange={(event) => setStarterCode(event.target.value)} rows={7} className="font-mono text-xs" /></div>
              <div className="space-y-3"><Label>Tests</Label>{tests.map((test, index) => <div key={index} className="space-y-2 rounded-md border border-[#1E2629] p-3"><div className="flex items-center justify-between gap-2"><Input value={test.name} onChange={(event) => updateTest(index, { name: event.target.value })} aria-label={`Nombre del test ${index + 1}`} /><Select value={test.visibility} onValueChange={(value: "PUBLIC" | "HIDDEN") => updateTest(index, { visibility: value })}><SelectTrigger className="w-32"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="PUBLIC">Público</SelectItem><SelectItem value="HIDDEN">Oculto</SelectItem></SelectContent></Select></div><Textarea value={test.stdin_data} onChange={(event) => updateTest(index, { stdin_data: event.target.value })} placeholder="Entrada stdin" aria-label={`Entrada del test ${index + 1}`} /><Textarea value={test.expected_stdout} onChange={(event) => updateTest(index, { expected_stdout: event.target.value })} placeholder="Salida esperada" aria-label={`Salida del test ${index + 1}`} /></div>)}</div>
              <div className="flex justify-end"><Button type="submit" disabled={saving || loading || !selectedSkill}>{saving ? "Guardando..." : "Guardar borrador"}</Button></div>
            </form>
          </CardContent>
        </Card>
        <Card className="border-[#1E2629] bg-[#141C1E] text-[#F0FDFA]"><CardHeader><CardTitle>Versiones creadas</CardTitle><CardDescription className="text-[#8B9D9F]">Publicá solo cuando haya tests públicos y ocultos.</CardDescription></CardHeader><CardContent className="space-y-3">{challenges.length === 0 ? <p className="text-sm text-[#8B9D9F]">Todavía no hay retos.</p> : challenges.map((challenge) => <div key={challenge.id} className="rounded-md border border-[#1E2629] p-3"><div className="flex items-start justify-between gap-2"><div><p className="font-semibold">{challenge.title}</p><p className="text-xs text-[#8B9D9F]">Nivel {challenge.level_number} · v{challenge.version}</p></div><Badge variant={challenge.status === "PUBLISHED" ? "default" : "outline"}>{challenge.status}</Badge></div>{challenge.status === "DRAFT" && <Button className="mt-3" size="sm" onClick={() => publishProgrammingChallenge(challenge.id).then(load)}>Publicar versión</Button>}</div>)}</CardContent></Card>
      </div>
    </div>
  )
}

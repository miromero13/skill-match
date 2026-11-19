import { useEffect, useRef, useState, type FormEvent } from "react"
import { getSkills } from "@/services/admin-catalog-service"
import { theoryBank, type QuestionContent, type TheoryQuestion } from "@/services/theory-bank-service"
import type { Skill } from "@/types/catalog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

const blank = (): QuestionContent => ({ kind: "OPEN", prompt: "", choices: [], correct_choice: null,
  reference_answer: "", criteria: [], time_limit_seconds: 90, max_score: 20 })
const failure = (error: unknown) => error instanceof Error ? error.message : "No se pudo completar la operación."

export function TheoryBankPage() {
  const [skills, setSkills] = useState<Skill[]>([])
  const [skill, setSkill] = useState("")
  const [level, setLevel] = useState(1)
  const [status, setStatus] = useState("ALL")
  const [offset, setOffset] = useState(0)
  const [items, setItems] = useState<TheoryQuestion[]>([])
  const [count, setCount] = useState(0)
  const [editing, setEditing] = useState<TheoryQuestion | null>(null)
  const [content, setContent] = useState<QuestionContent | null>(null)
  const [history, setHistory] = useState<TheoryQuestion[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")
  const [refresh, setRefresh] = useState(0)
  const mounted = useRef(true)
  const request = useRef(0)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  useEffect(() => {
    let active = true
    getSkills().then(result => {
      if (active) { setSkills(result.items); setSkill(result.items[0]?.id ?? "") }
    }).catch(reason => { if (active) setError(failure(reason)) })
    return () => { active = false }
  }, [])
  useEffect(() => {
    const generation = ++request.current
    setLoading(true)
    theoryBank.list({ skill_id: skill || undefined, level_number: level,
      status: status === "ALL" ? undefined : status, offset, limit: 20 }).then(result => {
      if (mounted.current && generation === request.current) { setItems(result.data); setCount(result.count ?? 0) }
    }).catch(reason => { if (mounted.current && generation === request.current) setError(failure(reason)) })
      .finally(() => { if (mounted.current && generation === request.current) setLoading(false) })
  }, [skill, level, status, offset, refresh])
  const update = (patch: Partial<QuestionContent>) => setContent(current => current ? { ...current, ...patch } : current)
  const run = async (operation: () => Promise<void>) => {
    if (busy) return
    setBusy(true); setError(""); setMessage("")
    try { await operation() } catch (reason) { if (mounted.current) setError(failure(reason)) }
    finally { if (mounted.current) setBusy(false) }
  }
  const save = (event: FormEvent) => {
    event.preventDefault()
    if (!content) return
    void run(async () => {
      const response = editing ? await theoryBank.edit(editing.id, editing.version, content)
        : await theoryBank.create({ ...content, skill_id: skill, level_number: level })
      if (mounted.current) { setMessage(response.message); setContent(null); setEditing(null); setRefresh(n => n + 1) }
    })
  }
  const mutate = (item: TheoryQuestion, action: "publish" | "archive") => void run(async () => {
    const response = await theoryBank[action](item.id, item.version)
    if (mounted.current) { setMessage(response.message); setRefresh(n => n + 1) }
  })
  const levels = skills.find(item => item.id === skill)?.levels ?? []
  return <div className="mx-auto grid w-full max-w-6xl gap-5 p-4 sm:p-6">
    <header className="flex flex-wrap items-center justify-between gap-3">
      <div><h1 className="text-2xl font-semibold">Banco de preguntas</h1><p>Prepará preguntas y rúbricas por habilidad y nivel. Publicá solo contenido revisado.</p></div>
      <Button disabled={busy || !skill || !levels.some(item => item.level_number === level)} onClick={() => { setEditing(null); setContent(blank()); setHistory(null) }}>Nueva pregunta</Button>
    </header>
    {error && <p role="alert" className="text-destructive">{error}</p>}
    {message && <p role="status">{message}</p>}
    <section aria-label="Filtros" className="grid gap-3 sm:grid-cols-3">
      <div><Label htmlFor="bank-skill">Habilidad</Label><Select value={skill} disabled={busy || !!content} onValueChange={value => { setSkill(value); setLevel(skills.find(item => item.id === value)?.levels[0]?.level_number ?? 1); setOffset(0) }}>
        <SelectTrigger id="bank-skill"><SelectValue placeholder="Seleccioná una habilidad" /></SelectTrigger><SelectContent>{skills.map(item => <SelectItem key={item.id} value={item.id}>{item.name}</SelectItem>)}</SelectContent></Select></div>
      <div><Label htmlFor="bank-level">Nivel</Label><Select value={String(level)} disabled={busy || !!content} onValueChange={value => { setLevel(Number(value)); setOffset(0) }}>
        <SelectTrigger id="bank-level"><SelectValue /></SelectTrigger><SelectContent>{levels.map(item => <SelectItem key={item.level_number} value={String(item.level_number)}>{item.name}</SelectItem>)}</SelectContent></Select></div>
      <div><Label htmlFor="bank-status">Estado</Label><Select value={status} disabled={busy} onValueChange={value => { setStatus(value); setOffset(0) }}>
        <SelectTrigger id="bank-status"><SelectValue /></SelectTrigger><SelectContent>{[["ALL", "Todos"], ["DRAFT", "Borrador"], ["PUBLISHED", "Publicada"], ["ARCHIVED", "Archivada"]].map(([value, text]) => <SelectItem key={value} value={value}>{text}</SelectItem>)}</SelectContent></Select></div>
    </section>
    {content && <Card><CardHeader><CardTitle>{editing ? `Editar versión ${editing.version}` : "Nuevo borrador"}</CardTitle></CardHeader><CardContent>
      <form onSubmit={save} className="grid gap-4"><fieldset disabled={busy} className="grid gap-4">
        <Label htmlFor="bank-kind">Tipo</Label><Select value={content.kind} onValueChange={value => update({ kind: value as QuestionContent["kind"], choices: value === "TRUE_FALSE" ? [{ code: "TRUE", text: "Verdadero" }, { code: "FALSE", text: "Falso" }] : [], correct_choice: null })}>
          <SelectTrigger id="bank-kind"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="OPEN">Abierta</SelectItem><SelectItem value="MULTIPLE_CHOICE">Opción múltiple</SelectItem><SelectItem value="TRUE_FALSE">Verdadero / falso</SelectItem></SelectContent></Select>
        <Label htmlFor="bank-prompt">Enunciado</Label><Textarea id="bank-prompt" required maxLength={4000} value={content.prompt} onChange={e => update({ prompt: e.target.value })} />
        {content.kind !== "OPEN" && <div className="grid gap-2">
          {content.choices.map((choice, index) => <div key={index} className="grid grid-cols-[5rem_1fr] gap-2">
            <Input aria-label={`Código opción ${index + 1}`} value={choice.code} maxLength={8} disabled={content.kind === "TRUE_FALSE"} onChange={e => update({ choices: content.choices.map((item, i) => i === index ? { ...item, code: e.target.value } : item) })} />
            <Input aria-label={`Texto opción ${index + 1}`} value={choice.text} maxLength={1000} onChange={e => update({ choices: content.choices.map((item, i) => i === index ? { ...item, text: e.target.value } : item) })} />
          </div>)}
          {content.kind === "MULTIPLE_CHOICE" && <Button type="button" variant="outline" disabled={content.choices.length >= 6} onClick={() => update({ choices: [...content.choices, { code: String.fromCharCode(65 + content.choices.length), text: "" }] })}>Agregar opción</Button>}
          <Label htmlFor="bank-correct">Código de respuesta correcta</Label><Input id="bank-correct" maxLength={8} value={content.correct_choice ?? ""} onChange={e => update({ correct_choice: e.target.value || null })} />
        </div>}
        <Label htmlFor="bank-reference">Respuesta de referencia</Label><Textarea id="bank-reference" maxLength={8000} value={content.reference_answer} onChange={e => update({ reference_answer: e.target.value })} />
        <p>La rúbrica debe sumar 100 para publicar. La justificación oral se evalúa contra estos criterios.</p>
        {content.criteria.map((criterion, index) => <div key={index} className="grid gap-2 rounded border p-3 sm:grid-cols-2">
          <Input aria-label={`Nombre criterio ${index + 1}`} value={criterion.name} maxLength={100} onChange={e => update({ criteria: content.criteria.map((item, i) => i === index ? { ...item, name: e.target.value } : item) })} />
          <Input aria-label={`Peso criterio ${index + 1}`} type="number" min={1} max={100} value={criterion.weight} onChange={e => update({ criteria: content.criteria.map((item, i) => i === index ? { ...item, weight: Number(e.target.value) } : item) })} />
          <Textarea aria-label={`Descripción criterio ${index + 1}`} value={criterion.description} maxLength={2000} onChange={e => update({ criteria: content.criteria.map((item, i) => i === index ? { ...item, description: e.target.value } : item) })} />
          <Button type="button" variant="outline" onClick={() => update({ criteria: content.criteria.filter((_, i) => i !== index) })}>Quitar criterio {index + 1}</Button>
        </div>)}
        <Button type="button" variant="outline" disabled={content.criteria.length >= 12} onClick={() => update({ criteria: [...content.criteria, { name: "", weight: 100, description: "" }] })}>Agregar criterio</Button>
        <Label htmlFor="bank-time">Tiempo máximo (segundos)</Label><Input id="bank-time" type="number" min={1} max={300} required value={content.time_limit_seconds} onChange={e => update({ time_limit_seconds: Number(e.target.value) })} />
        <Label htmlFor="bank-score">Puntaje máximo</Label><Input id="bank-score" type="number" min={1} max={100} required value={content.max_score} onChange={e => update({ max_score: Number(e.target.value) })} />
        <div className="flex gap-2"><Button type="submit">Guardar borrador</Button><Button type="button" variant="outline" onClick={() => setContent(null)}>Cancelar</Button></div>
      </fieldset></form>
    </CardContent></Card>}
    {loading ? <p role="status">Cargando preguntas…</p> : items.length === 0 ? <p>No hay preguntas para estos filtros.</p> : items.map(item => <Card key={item.id}><CardHeader><CardTitle>{item.content.prompt}</CardTitle><Badge>{item.status} · v{item.version}</Badge></CardHeader><CardContent className="flex flex-wrap gap-2">
      <Button variant="outline" disabled={busy} onClick={() => { setEditing(item); setContent(structuredClone(item.content)); setHistory(null) }}>Editar</Button>
      <Button disabled={busy || item.status === "PUBLISHED"} onClick={() => mutate(item, "publish")}>Publicar</Button>
      <Button variant="outline" disabled={busy || item.status === "ARCHIVED"} onClick={() => mutate(item, "archive")}>Archivar</Button>
      <Button variant="outline" disabled={busy} onClick={() => void run(async () => { const result = await theoryBank.history(item.id); if (mounted.current) setHistory(result.data) })}>Historial</Button>
    </CardContent></Card>)}
    <nav aria-label="Paginación" className="flex flex-wrap items-center gap-3"><Button variant="outline" disabled={busy || loading || offset === 0} onClick={() => setOffset(n => Math.max(0, n - 20))}>Anterior</Button><span>{count} preguntas</span><Button variant="outline" disabled={busy || loading || offset + 20 >= count} onClick={() => setOffset(n => n + 20)}>Siguiente</Button></nav>
    {history && <section aria-label="Historial de versiones"><h2 className="text-lg font-semibold">Historial inmutable</h2>{history.map(item => <Card key={item.version}><CardContent className="grid gap-2 py-4"><h3>Versión {item.version} · {item.status}</h3><p>{item.content.prompt}</p><p>{item.content.reference_answer}</p>{item.content.criteria.map((criterion, index) => <p key={index}>{criterion.name}: {criterion.weight}% — {criterion.description}</p>)}</CardContent></Card>)}</section>}
  </div>
}

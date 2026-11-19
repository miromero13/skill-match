import { useEffect, useMemo, useRef, useState, type FormEvent } from "react"
import { getSkills } from "@/services/admin-catalog-service"
import { theoryBank, type QuestionContent, type TheoryQuestion } from "@/services/theory-bank-service"
import type { Skill, SkillLevel } from "@/types/catalog"
import {
  Plus,
  BookOpen,
  CheckCircle2,
  Clock,
  Archive,
  History,
  Edit3,
  Trash2,
  AlertCircle,
  Sparkles,
  FileText,
  Scale,
  Timer,
  Award,
  Layers,
  X,
  Send,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

const CANONICAL_LEVELS_FALLBACK: SkillLevel[] = [
  { level_number: 1, name: "Principiante" },
  { level_number: 2, name: "Elemental" },
  { level_number: 3, name: "Intermedio" },
  { level_number: 4, name: "Avanzado" },
  { level_number: 5, name: "Master Pedagogo" },
]

const KIND_META: Record<
  QuestionContent["kind"],
  { label: string; description: string; badgeClass: string }
> = {
  OPEN: {
    label: "Abierta (Oral /Desarrollo)",
    description: "El postulante responde libremente y la IA evalúa contra la respuesta de referencia y rúbrica.",
    badgeClass: "bg-teal-500/15 text-[#2DD4BF] border-teal-500/30",
  },
  MULTIPLE_CHOICE: {
    label: "Opción múltiple",
    description: "Pregunta con 2 a 6 alternativas únicas, una opción correcta y justificación evaluada por rúbrica.",
    badgeClass: "bg-indigo-500/15 text-indigo-300 border-indigo-500/30",
  },
  TRUE_FALSE: {
    label: "Verdadero / Falso",
    description: "Afirmación binaria (TRUE / FALSE) acompañada de justificación conceptual evaluada por rúbrica.",
    badgeClass: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  },
}

const STATUS_META: Record<
  TheoryQuestion["status"],
  { label: string; badgeClass: string; icon: typeof Clock }
> = {
  DRAFT: {
    label: "Borrador",
    badgeClass: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    icon: Clock,
  },
  PUBLISHED: {
    label: "Publicada",
    badgeClass: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    icon: CheckCircle2,
  },
  ARCHIVED: {
    label: "Archivada",
    badgeClass: "bg-slate-500/15 text-slate-300 border-slate-500/30",
    icon: Archive,
  },
}

const blank = (): QuestionContent => ({
  kind: "OPEN",
  prompt: "",
  choices: [],
  correct_choice: null,
  reference_answer: "",
  criteria: [],
  time_limit_seconds: 90,
  max_score: 20,
})

const failure = (error: unknown) =>
  error instanceof Error ? error.message : "No se pudo completar la operación."

function resolveSkillLevels(selectedSkill?: Skill): SkillLevel[] {
  if (selectedSkill?.levels && selectedSkill.levels.length > 0) {
    return selectedSkill.levels
  }
  return CANONICAL_LEVELS_FALLBACK
}

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

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  useEffect(() => {
    let active = true
    getSkills()
      .then((result) => {
        if (active) {
          setSkills(result.items)
          const firstSkill = result.items[0]
          setSkill(firstSkill?.id ?? "")
          const firstLevels = resolveSkillLevels(firstSkill)
          setLevel(firstLevels[0]?.level_number ?? 1)
        }
      })
      .catch((reason) => {
        if (active) setError(failure(reason))
      })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    const generation = ++request.current
    setLoading(true)
    theoryBank
      .list({
        skill_id: skill || undefined,
        level_number: level,
        status: status === "ALL" ? undefined : status,
        offset,
        limit: 20,
      })
      .then((result) => {
        if (mounted.current && generation === request.current) {
          setItems(result.data)
          setCount(result.count ?? 0)
        }
      })
      .catch((reason) => {
        if (mounted.current && generation === request.current) setError(failure(reason))
      })
      .finally(() => {
        if (mounted.current && generation === request.current) setLoading(false)
      })
  }, [skill, level, status, offset, refresh])

  const selectedSkillObj = useMemo(
    () => skills.find((item) => item.id === skill),
    [skills, skill]
  )

  const levels = useMemo(
    () => resolveSkillLevels(selectedSkillObj),
    [selectedSkillObj]
  )

  const currentLevelObj = useMemo(
    () => levels.find((item) => item.level_number === level) ?? levels[0],
    [levels, level]
  )

  const stats = useMemo(() => {
    const published = items.filter((i) => i.status === "PUBLISHED").length
    const draft = items.filter((i) => i.status === "DRAFT").length
    const archived = items.filter((i) => i.status === "ARCHIVED").length
    return { total: count, published, draft, archived }
  }, [items, count])

  const criteriaTotalWeight = useMemo(() => {
    if (!content) return 0
    return content.criteria.reduce((acc, item) => acc + (Number(item.weight) || 0), 0)
  }, [content])

  const update = (patch: Partial<QuestionContent>) =>
    setContent((current) => (current ? { ...current, ...patch } : current))

  const run = async (operation: () => Promise<void>) => {
    if (busy) return
    setBusy(true)
    setError("")
    setMessage("")
    try {
      await operation()
    } catch (reason) {
      if (mounted.current) setError(failure(reason))
    } finally {
      if (mounted.current) setBusy(false)
    }
  }

  const save = (event: FormEvent) => {
    event.preventDefault()
    if (!content) return
    void run(async () => {
      const response = editing
        ? await theoryBank.edit(editing.id, editing.version, content)
        : await theoryBank.create({ ...content, skill_id: skill, level_number: level })
      if (mounted.current) {
        setMessage(response.message)
        setContent(null)
        setEditing(null)
        setRefresh((n) => n + 1)
      }
    })
  }

  const mutate = (item: TheoryQuestion, action: "publish" | "archive") =>
    void run(async () => {
      const response = await theoryBank[action](item.id, item.version)
      if (mounted.current) {
        setMessage(response.message)
        setRefresh((n) => n + 1)
      }
    })

  const loadRubricFromSkillLevel = () => {
    if (!content) return
    const levelRubric = currentLevelObj?.rubric?.criteria
    if (levelRubric && levelRubric.length > 0) {
      update({
        criteria: levelRubric.map((c) => ({
          name: c.name,
          weight: c.weight,
          description: c.description,
        })),
      })
    } else {
      update({
        criteria: [
          {
            name: "Dominio Conceptual",
            weight: 50,
            description: "Precisión teórica y uso correcto de terminología técnica.",
          },
          {
            name: "Claridad y Justificación",
            weight: 50,
            description: "Coherencia argumentativa y aplicación práctica del concepto.",
          },
        ],
      })
    }
  }

  return (
    <div className="mx-auto w-full max-w-7xl space-y-6 p-4 md:p-8">
      {/* Header Principal */}
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#1E2629] pb-6">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <Badge className="bg-[#00786F]/20 text-[#2DD4BF] border-[#00786F]/40 text-[11px] font-bold uppercase tracking-wider">
              Evaluación Teórica & Defensa Oral
            </Badge>
            {selectedSkillObj && (
              <Badge variant="outline" className="border-[#1E2629] bg-[#141C1E] text-[#8B9D9F] text-xs">
                {selectedSkillObj.name} · Nivel {level} ({currentLevelObj?.name || `Nivel ${level}`})
              </Badge>
            )}
          </div>
          <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-[#F0FDFA]">
            Banco de preguntas
          </h1>
          <p className="text-sm text-[#8B9D9F] max-w-2xl leading-relaxed">
            Prepará preguntas y rúbricas por habilidad y nivel. Publicá solo contenido revisado. Se requieren al menos 5 preguntas publicadas por nivel para habilitar exámenes teóricos.
          </p>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          <Button
            disabled={busy || !skill || !levels.some((item) => item.level_number === level)}
            onClick={() => {
              setEditing(null)
              setContent(blank())
              setHistory(null)
            }}
            className="bg-[#00786F] hover:bg-[#00665E] text-[#F0FDFA] font-bold flex items-center gap-1.5 cursor-pointer shadow-xs"
          >
            <Plus className="h-4 w-4" />
            <span>Nueva pregunta</span>
          </Button>
        </div>
      </header>

      {/* Alertas de estado / error del servidor */}
      {error && (
        <div
          role="alert"
          className="flex items-center justify-between gap-3 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300 shadow-xs"
        >
          <div className="flex items-center gap-2.5">
            <AlertCircle className="h-4 w-4 shrink-0 text-red-400" />
            <span>{error}</span>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={() => setError("")}
            className="h-7 w-7 text-red-300 hover:text-white hover:bg-red-500/20"
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      )}

      {message && (
        <div
          role="status"
          className="flex items-center justify-between gap-3 rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300 shadow-xs"
        >
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
            <span>{message}</span>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={() => setMessage("")}
            className="h-7 w-7 text-emerald-300 hover:text-white hover:bg-emerald-500/20"
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      )}

      {/* Indicadores de Cobertura del Nivel Actual */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-[#141C1E] border border-[#1E2629] rounded-xl p-4 flex items-center gap-3 shadow-xs">
          <div className="p-2.5 rounded-lg bg-[#1A2225] text-[#2DD4BF] border border-[#1E2629]">
            <BookOpen className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs text-[#8B9D9F] font-medium">Total en este filtro</p>
            <p className="text-xl font-bold text-[#F0FDFA]">{stats.total}</p>
          </div>
        </div>

        <div className="bg-[#141C1E] border border-[#1E2629] rounded-xl p-4 flex items-center gap-3 shadow-xs">
          <div className="p-2.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs text-[#8B9D9F] font-medium">Publicadas (mín. 5)</p>
            <div className="flex items-center gap-2">
              <p className="text-xl font-bold text-[#F0FDFA]">{stats.published}</p>
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${
                  stats.published >= 5
                    ? "bg-emerald-500/20 text-emerald-300"
                    : "bg-amber-500/20 text-amber-300"
                }`}
              >
                {stats.published >= 5 ? "Examen listo" : `Faltan ${Math.max(0, 5 - stats.published)}`}
              </span>
            </div>
          </div>
        </div>

        <div className="bg-[#141C1E] border border-[#1E2629] rounded-xl p-4 flex items-center gap-3 shadow-xs">
          <div className="p-2.5 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Clock className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs text-[#8B9D9F] font-medium">En borrador</p>
            <p className="text-xl font-bold text-[#F0FDFA]">{stats.draft}</p>
          </div>
        </div>

        <div className="bg-[#141C1E] border border-[#1E2629] rounded-xl p-4 flex items-center gap-3 shadow-xs">
          <div className="p-2.5 rounded-lg bg-slate-500/10 text-slate-400 border border-slate-500/20">
            <Archive className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs text-[#8B9D9F] font-medium">Archivadas</p>
            <p className="text-xl font-bold text-[#F0FDFA]">{stats.archived}</p>
          </div>
        </div>
      </div>

      {/* Barra de Filtros con Escalera de Niveles */}
      <section
        aria-label="Filtros"
        className="space-y-4 rounded-xl border border-[#1E2629] bg-[#141C1E] p-4 sm:p-5 shadow-xs"
      >
        <div className="grid gap-4 sm:grid-cols-3">
          {/* Selector de Habilidad */}
          <div className="space-y-1.5">
            <Label htmlFor="bank-skill" className="text-xs font-semibold text-[#8B9D9F] uppercase tracking-wider">
              Habilidad
            </Label>
            <Select
              value={skill}
              disabled={busy || !!content}
              onValueChange={(value) => {
                setSkill(value)
                const found = skills.find((item) => item.id === value)
                const nextLevels = resolveSkillLevels(found)
                setLevel(nextLevels[0]?.level_number ?? 1)
                setOffset(0)
              }}
            >
              <SelectTrigger
                id="bank-skill"
                className="w-full bg-[#0F1416] border-[#1E2629] text-[#F0FDFA]"
              >
                <SelectValue placeholder="Seleccioná una habilidad" />
              </SelectTrigger>
              <SelectContent className="bg-[#141C1E] border-[#1E2629] text-[#F0FDFA]">
                {skills.map((item) => (
                  <SelectItem key={item.id} value={item.id}>
                    {item.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Selector de Nivel */}
          <div className="space-y-1.5">
            <Label htmlFor="bank-level" className="text-xs font-semibold text-[#8B9D9F] uppercase tracking-wider">
              Nivel
            </Label>
            <Select
              value={String(level)}
              disabled={busy || !!content}
              onValueChange={(value) => {
                setLevel(Number(value))
                setOffset(0)
              }}
            >
              <SelectTrigger
                id="bank-level"
                className="w-full bg-[#0F1416] border-[#1E2629] text-[#F0FDFA]"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-[#141C1E] border-[#1E2629] text-[#F0FDFA]">
                {levels.map((item) => (
                  <SelectItem key={item.level_number} value={String(item.level_number)}>
                    {item.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Selector de Estado */}
          <div className="space-y-1.5">
            <Label htmlFor="bank-status" className="text-xs font-semibold text-[#8B9D9F] uppercase tracking-wider">
              Estado
            </Label>
            <Select
              value={status}
              disabled={busy}
              onValueChange={(value) => {
                setStatus(value)
                setOffset(0)
              }}
            >
              <SelectTrigger
                id="bank-status"
                className="w-full bg-[#0F1416] border-[#1E2629] text-[#F0FDFA]"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-[#141C1E] border-[#1E2629] text-[#F0FDFA]">
                {[
                  ["ALL", "Todos"],
                  ["DRAFT", "Borrador"],
                  ["PUBLISHED", "Publicada"],
                  ["ARCHIVED", "Archivada"],
                ].map(([value, text]) => (
                  <SelectItem key={value} value={value}>
                    {text}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Botonera rápida de Escalera de Niveles */}
        {levels.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 pt-3 border-t border-[#1E2629]/70">
            <span className="text-xs font-medium text-[#8B9D9F] flex items-center gap-1.5 mr-1">
              <Layers className="h-3.5 w-3.5 text-[#2DD4BF]" />
              Escalera de niveles:
            </span>
            {levels.map((lvl) => {
              const isSelected = lvl.level_number === level
              return (
                <Button
                  key={lvl.level_number}
                  type="button"
                  variant={isSelected ? "default" : "outline"}
                  size="sm"
                  disabled={busy || !!content}
                  onClick={() => {
                    setLevel(lvl.level_number)
                    setOffset(0)
                  }}
                  className={
                    isSelected
                      ? "h-7 px-3 text-xs font-bold bg-[#00786F] hover:bg-[#00665E] text-white cursor-pointer"
                      : "h-7 px-3 text-xs border-[#1E2629] bg-[#0F1416] text-[#8B9D9F] hover:text-[#F0FDFA] hover:bg-[#1A2225] cursor-pointer"
                  }
                >
                  {lvl.level_number}. {lvl.name}
                </Button>
              )
            })}
          </div>
        )}
      </section>

      {/* Editor de Pregunta (Crear o Editar Versión) */}
      {content && (
        <Card className="border-[#00786F]/50 bg-[#141C1E] text-[#F0FDFA] shadow-xl rounded-2xl overflow-hidden">
          <CardHeader className="border-b border-[#1E2629] bg-[#0F1416] px-6 py-4 flex flex-row items-center justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-[#2DD4BF]" />
                <CardTitle className="text-base font-bold text-[#F0FDFA] uppercase tracking-tight">
                  {editing ? `Editar versión ${editing.version}` : "Nuevo borrador"}
                </CardTitle>
                <Badge className="bg-[#1A2225] text-[#2DD4BF] border-[#1E2629] text-xs">
                  {selectedSkillObj?.name || "Habilidad"} · Nivel {level} ({currentLevelObj?.name})
                </Badge>
              </div>
              <CardDescription className="text-xs text-[#8B9D9F]">
                Cada edición genera una revisión inmutable. Podés guardar un borrador parcial y completar la rúbrica antes de publicar.
              </CardDescription>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              disabled={busy}
              onClick={() => {
                setContent(null)
                setEditing(null)
              }}
              className="h-8 w-8 text-[#8B9D9F] hover:text-[#F0FDFA] hover:bg-[#1A2225]"
            >
              <X className="h-4 w-4" />
            </Button>
          </CardHeader>

          <CardContent className="p-6">
            <form onSubmit={save} className="space-y-6">
              <fieldset disabled={busy} className="space-y-6">
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
                  {/* Columna Izquierda: Configuración del Enunciado y Respuesta (7 cols) */}
                  <div className="lg:col-span-7 space-y-5 bg-[#0F1416] p-5 rounded-xl border border-[#1E2629]">
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                      <div className="sm:col-span-1 space-y-1.5">
                        <Label htmlFor="bank-kind" className="text-xs font-semibold text-[#8B9D9F] uppercase tracking-wider">
                          Tipo
                        </Label>
                        <Select
                          value={content.kind}
                          onValueChange={(value) =>
                            update({
                              kind: value as QuestionContent["kind"],
                              choices:
                                value === "TRUE_FALSE"
                                  ? [
                                      { code: "TRUE", text: "Verdadero" },
                                      { code: "FALSE", text: "Falso" },
                                    ]
                                  : value === "MULTIPLE_CHOICE" && content.choices.length === 0
                                  ? [
                                      { code: "A", text: "" },
                                      { code: "B", text: "" },
                                    ]
                                  : [],
                              correct_choice: value === "TRUE_FALSE" ? "TRUE" : null,
                            })
                          }
                        >
                          <SelectTrigger id="bank-kind" className="bg-[#141C1E] border-[#1E2629] text-[#F0FDFA]">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent className="bg-[#141C1E] border-[#1E2629] text-[#F0FDFA]">
                            <SelectItem value="OPEN">Abierta</SelectItem>
                            <SelectItem value="MULTIPLE_CHOICE">Opción múltiple</SelectItem>
                            <SelectItem value="TRUE_FALSE">Verdadero / falso</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      <div className="sm:col-span-1 space-y-1.5">
                        <Label htmlFor="bank-time" className="text-xs font-semibold text-[#8B9D9F] uppercase tracking-wider">
                          Tiempo máximo (segundos)
                        </Label>
                        <Input
                          id="bank-time"
                          type="number"
                          min={1}
                          max={300}
                          required
                          value={content.time_limit_seconds}
                          onChange={(e) => update({ time_limit_seconds: Number(e.target.value) })}
                          className="bg-[#141C1E] border-[#1E2629] text-[#F0FDFA]"
                        />
                      </div>

                      <div className="sm:col-span-1 space-y-1.5">
                        <Label htmlFor="bank-score" className="text-xs font-semibold text-[#8B9D9F] uppercase tracking-wider">
                          Puntaje máximo
                        </Label>
                        <Input
                          id="bank-score"
                          type="number"
                          min={1}
                          max={100}
                          required
                          value={content.max_score}
                          onChange={(e) => update({ max_score: Number(e.target.value) })}
                          className="bg-[#141C1E] border-[#1E2629] text-[#2DD4BF] font-bold"
                        />
                      </div>
                    </div>

                    <p className="text-xs text-[#8B9D9F] bg-[#141C1E] px-3 py-2 rounded-lg border border-[#1E2629]">
                      {KIND_META[content.kind].description}
                    </p>

                    {/* Enunciado */}
                    <div className="space-y-1.5">
                      <Label htmlFor="bank-prompt" className="text-xs font-semibold text-[#8B9D9F] uppercase tracking-wider">
                        Enunciado
                      </Label>
                      <Textarea
                        id="bank-prompt"
                        required
                        maxLength={4000}
                        rows={3}
                        placeholder="Ej: Explicá la diferencia entre estructuras mutables e inmutables en Python y cuándo conviene usar cada una..."
                        value={content.prompt}
                        onChange={(e) => update({ prompt: e.target.value })}
                        className="bg-[#141C1E] border-[#1E2629] text-[#F0FDFA] placeholder:text-[#67787C]"
                      />
                    </div>

                    {/* Opciones para MULTIPLE_CHOICE o TRUE_FALSE */}
                    {content.kind !== "OPEN" && (
                      <div className="space-y-3 rounded-xl border border-[#1E2629] bg-[#141C1E] p-4">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-[#F0FDFA] uppercase tracking-wider">
                            Opciones de Respuesta ({content.choices.length}/6)
                          </span>
                          {content.kind === "MULTIPLE_CHOICE" && (
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              disabled={content.choices.length >= 6}
                              onClick={() =>
                                update({
                                  choices: [
                                    ...content.choices,
                                    {
                                      code: String.fromCharCode(65 + content.choices.length),
                                      text: "",
                                    },
                                  ],
                                })
                              }
                              className="h-7 text-xs border-[#1E2629] bg-[#0F1416] text-[#2DD4BF] hover:bg-[#1A2225]"
                            >
                              <Plus className="h-3.5 w-3.5 mr-1" />
                              Agregar opción
                            </Button>
                          )}
                        </div>

                        <div className="space-y-2">
                          {content.choices.map((choice, index) => (
                            <div key={index} className="grid grid-cols-[5.5rem_1fr_auto] items-center gap-2">
                              <Input
                                aria-label={`Código opción ${index + 1}`}
                                value={choice.code}
                                maxLength={8}
                                placeholder="Cód."
                                disabled={content.kind === "TRUE_FALSE"}
                                onChange={(e) =>
                                  update({
                                    choices: content.choices.map((item, i) =>
                                      i === index ? { ...item, code: e.target.value } : item
                                    ),
                                  })
                                }
                                className="bg-[#0F1416] border-[#1E2629] text-center font-mono text-xs font-bold text-[#2DD4BF]"
                              />
                              <Input
                                aria-label={`Texto opción ${index + 1}`}
                                value={choice.text}
                                maxLength={1000}
                                placeholder={`Texto de la alternativa ${choice.code || index + 1}...`}
                                onChange={(e) =>
                                  update({
                                    choices: content.choices.map((item, i) =>
                                      i === index ? { ...item, text: e.target.value } : item
                                    ),
                                  })
                                }
                                className="bg-[#0F1416] border-[#1E2629] text-[#F0FDFA] text-xs"
                              />
                              {content.kind === "MULTIPLE_CHOICE" && content.choices.length > 2 && (
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="icon"
                                  onClick={() =>
                                    update({
                                      choices: content.choices.filter((_, i) => i !== index),
                                    })
                                  }
                                  className="h-8 w-8 text-[#8B9D9F] hover:text-red-400"
                                  title="Quitar opción"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </Button>
                              )}
                            </div>
                          ))}
                        </div>

                        <div className="pt-2 border-t border-[#1E2629] space-y-1.5">
                          <Label htmlFor="bank-correct" className="text-xs font-semibold text-[#8B9D9F] uppercase tracking-wider">
                            Código de respuesta correcta
                          </Label>
                          <Input
                            id="bank-correct"
                            maxLength={8}
                            placeholder={content.kind === "TRUE_FALSE" ? "TRUE o FALSE" : "Ej: A"}
                            value={content.correct_choice ?? ""}
                            onChange={(e) => update({ correct_choice: e.target.value || null })}
                            className="bg-[#0F1416] border-[#1E2629] font-mono text-xs font-bold text-emerald-400"
                          />
                        </div>
                      </div>
                    )}

                    {/* Respuesta de referencia */}
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <Label htmlFor="bank-reference" className="text-xs font-semibold text-[#8B9D9F] uppercase tracking-wider">
                          Respuesta de referencia (Guía para el Corrector IA)
                        </Label>
                        <span className="text-[11px] text-[#67787C]">Requerida para publicar</span>
                      </div>
                      <Textarea
                        id="bank-reference"
                        maxLength={8000}
                        rows={4}
                        placeholder="Escribí la respuesta modelo o los puntos clave que el postulante debe mencionar durante su justificación..."
                        value={content.reference_answer}
                        onChange={(e) => update({ reference_answer: e.target.value })}
                        className="bg-[#141C1E] border-[#1E2629] text-[#F0FDFA] placeholder:text-[#67787C]"
                      />
                    </div>
                  </div>

                  {/* Columna Derecha: Rúbrica y Criterios de Evaluación (5 cols) */}
                  <div className="lg:col-span-5 space-y-4 bg-[#0F1416] p-5 rounded-xl border border-[#1E2629]">
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#1E2629] pb-3">
                      <div>
                        <h3 className="text-xs font-bold text-[#F0FDFA] uppercase tracking-wider flex items-center gap-1.5">
                          <Scale className="h-4 w-4 text-[#2DD4BF]" />
                          Rúbrica de Evaluación ({content.criteria.length}/12)
                        </h3>
                        <p className="text-[11px] text-[#8B9D9F] mt-0.5">
                          La rúbrica debe sumar 100 para publicar. La justificación oral se evalúa contra estos criterios.
                        </p>
                      </div>

                      <Badge
                        className={`text-xs font-bold ${
                          Math.abs(criteriaTotalWeight - 100) < 0.01
                            ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
                            : "bg-amber-500/20 text-amber-300 border-amber-500/40"
                        }`}
                      >
                        Suma: {criteriaTotalWeight}% / 100%
                      </Badge>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={content.criteria.length >= 12}
                        onClick={() =>
                          update({
                            criteria: [
                              ...content.criteria,
                              {
                                name: "",
                                weight: Math.max(1, 100 - criteriaTotalWeight),
                                description: "",
                              },
                            ],
                          })
                        }
                        className="h-8 text-xs border-[#1E2629] bg-[#141C1E] text-[#2DD4BF] hover:bg-[#1A2225] cursor-pointer"
                      >
                        <Plus className="h-3.5 w-3.5 mr-1" />
                        Agregar criterio
                      </Button>

                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={loadRubricFromSkillLevel}
                        className="h-8 text-xs text-[#8B9D9F] hover:text-[#F0FDFA] hover:bg-[#141C1E] cursor-pointer"
                      >
                        <Sparkles className="h-3.5 w-3.5 mr-1 text-[#2DD4BF]" />
                        Usar plantilla de nivel
                      </Button>
                    </div>

                    {content.criteria.length === 0 ? (
                      <div className="rounded-xl border border-dashed border-[#1E2629] bg-[#141C1E] p-6 text-center space-y-2">
                        <Scale className="h-7 w-7 text-[#67787C] mx-auto" />
                        <p className="text-xs font-medium text-[#F0FDFA]">Sin criterios cargados todavía</p>
                        <p className="text-[11px] text-[#8B9D9F]">
                          Agregá criterios manualmente o cargá la plantilla sugerida para que sumen 100%.
                        </p>
                      </div>
                    ) : (
                      <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
                        {content.criteria.map((criterion, index) => (
                          <div
                            key={index}
                            className="space-y-2.5 rounded-xl border border-[#1E2629] bg-[#141C1E] p-3.5"
                          >
                            <div className="grid grid-cols-[1fr_5.5rem] gap-2">
                              <Input
                                aria-label={`Nombre criterio ${index + 1}`}
                                placeholder={`Nombre del criterio ${index + 1}`}
                                value={criterion.name}
                                maxLength={100}
                                onChange={(e) =>
                                  update({
                                    criteria: content.criteria.map((item, i) =>
                                      i === index ? { ...item, name: e.target.value } : item
                                    ),
                                  })
                                }
                                className="h-8 bg-[#0F1416] border-[#1E2629] text-xs text-[#F0FDFA]"
                              />
                              <div className="relative flex items-center">
                                <Input
                                  aria-label={`Peso criterio ${index + 1}`}
                                  type="number"
                                  min={1}
                                  max={100}
                                  value={criterion.weight}
                                  onChange={(e) =>
                                    update({
                                      criteria: content.criteria.map((item, i) =>
                                        i === index ? { ...item, weight: Number(e.target.value) } : item
                                      ),
                                    })
                                  }
                                  className="h-8 bg-[#0F1416] border-[#1E2629] pr-6 text-right text-xs font-bold text-[#2DD4BF]"
                                />
                                <span className="pointer-events-none absolute right-2 text-[11px] font-bold text-[#8B9D9F]">
                                  %
                                </span>
                              </div>
                            </div>

                            <Textarea
                              aria-label={`Descripción criterio ${index + 1}`}
                              placeholder="¿Qué aspecto específico se evalúa en este criterio?"
                              rows={2}
                              value={criterion.description}
                              maxLength={2000}
                              onChange={(e) =>
                                update({
                                  criteria: content.criteria.map((item, i) =>
                                    i === index ? { ...item, description: e.target.value } : item
                                  ),
                                })
                              }
                              className="bg-[#0F1416] border-[#1E2629] text-xs text-[#F0FDFA]"
                            />

                            <div className="flex justify-end">
                              <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                onClick={() =>
                                  update({
                                    criteria: content.criteria.filter((_, i) => i !== index),
                                  })
                                }
                                className="h-7 text-xs border-red-500/30 bg-[#0F1416] text-red-400 hover:bg-red-500/10"
                              >
                                <Trash2 className="h-3 w-3 mr-1" />
                                Quitar criterio {index + 1}
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* Pie del Formulario */}
                <div className="flex flex-wrap items-center justify-end gap-3 border-t border-[#1E2629] pt-4">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      setContent(null)
                      setEditing(null)
                    }}
                    className="border-[#1E2629] bg-[#0F1416] text-[#F0FDFA] hover:bg-[#1A2225] cursor-pointer"
                  >
                    Cancelar
                  </Button>
                  <Button
                    type="submit"
                    className="bg-[#00786F] hover:bg-[#00665E] text-white font-bold cursor-pointer"
                  >
                    Guardar borrador
                  </Button>
                </div>
              </fieldset>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Listado de Preguntas */}
      {loading ? (
        <div
          role="status"
          className="flex flex-col items-center justify-center rounded-2xl border border-[#1E2629] bg-[#141C1E] p-16 text-[#8B9D9F]"
        >
          <p className="text-sm font-medium">Cargando preguntas…</p>
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-[#1E2629] bg-[#141C1E] p-14 text-center space-y-3">
          <div className="p-3 rounded-full bg-[#1A2225] text-[#2DD4BF] border border-[#1E2629]">
            <FileText className="h-8 w-8" />
          </div>
          <div className="space-y-1 max-w-md">
            <h3 className="text-base font-bold text-[#F0FDFA]">No hay preguntas para estos filtros.</h3>
            <p className="text-xs text-[#8B9D9F]">
              Podés crear la primera pregunta para{" "}
              <strong className="text-[#F0FDFA]">{selectedSkillObj?.name || "esta habilidad"}</strong> en el{" "}
              <strong className="text-[#2DD4BF]">
                Nivel {level} ({currentLevelObj?.name || `Nivel ${level}`})
              </strong>{" "}
              haciendo clic en el botón inferior.
            </p>
          </div>
          <Button
            disabled={busy || !skill || !levels.some((item) => item.level_number === level)}
            onClick={() => {
              setEditing(null)
              setContent(blank())
              setHistory(null)
            }}
            className="mt-2 bg-[#00786F] hover:bg-[#00665E] text-white font-bold cursor-pointer"
          >
            <Plus className="h-4 w-4 mr-1.5" />
            Crear primera pregunta en este nivel
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {items.map((item) => {
            const kindInfo = KIND_META[item.content.kind] || KIND_META.OPEN
            const statusInfo = STATUS_META[item.status] || STATUS_META.DRAFT
            const StatusIcon = statusInfo.icon
            const weightSum = item.content.criteria.reduce((s, c) => s + (Number(c.weight) || 0), 0)
            const hasReference = Boolean(item.content.reference_answer?.trim())
            const isReadyToPublish = hasReference && item.content.criteria.length > 0 && Math.abs(weightSum - 100) < 0.01

            return (
              <Card
                key={item.id}
                className="border-[#1E2629] bg-[#141C1E] hover:border-[#00786F]/40 transition-colors text-[#F0FDFA] rounded-xl shadow-xs"
              >
                <CardHeader className="pb-3 flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                  <div className="space-y-2 flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge className={`text-xs font-semibold ${statusInfo.badgeClass}`}>
                        <StatusIcon className="h-3 w-3 mr-1" />
                        {statusInfo.label} · {item.status} · v{item.version}
                      </Badge>
                      <Badge className={`text-xs ${kindInfo.badgeClass}`}>
                        {kindInfo.label}
                      </Badge>
                      <Badge variant="outline" className="border-[#1E2629] bg-[#0F1416] text-[#8B9D9F] text-xs">
                        <Timer className="h-3 w-3 mr-1 text-[#2DD4BF]" />
                        {item.content.time_limit_seconds}s
                      </Badge>
                      <Badge variant="outline" className="border-[#1E2629] bg-[#0F1416] text-[#8B9D9F] text-xs">
                        <Award className="h-3 w-3 mr-1 text-[#2DD4BF]" />
                        {item.content.max_score} pts
                      </Badge>
                    </div>

                    <CardTitle className="text-base font-bold text-[#F0FDFA] leading-snug">
                      {item.content.prompt}
                    </CardTitle>
                  </div>

                  {/* Botones de Acción */}
                  <div className="flex flex-wrap items-center gap-2 shrink-0">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={busy}
                      onClick={() => {
                        setEditing(item)
                        setContent(structuredClone(item.content))
                        setHistory(null)
                      }}
                      className="h-8 border-[#1E2629] bg-[#0F1416] text-[#F0FDFA] hover:bg-[#1A2225] text-xs cursor-pointer"
                    >
                      <Edit3 className="h-3.5 w-3.5 mr-1.5 text-[#2DD4BF]" />
                      Editar
                    </Button>
                    <Button
                      size="sm"
                      disabled={busy || item.status === "PUBLISHED"}
                      onClick={() => mutate(item, "publish")}
                      className="h-8 bg-[#00786F] hover:bg-[#00665E] text-white font-semibold text-xs cursor-pointer"
                    >
                      <Send className="h-3.5 w-3.5 mr-1.5" />
                      Publicar
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={busy || item.status === "ARCHIVED"}
                      onClick={() => mutate(item, "archive")}
                      className="h-8 border-[#1E2629] bg-[#0F1416] text-[#8B9D9F] hover:text-[#F0FDFA] hover:bg-[#1A2225] text-xs cursor-pointer"
                    >
                      <Archive className="h-3.5 w-3.5 mr-1.5" />
                      Archivar
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={busy}
                      onClick={() =>
                        void run(async () => {
                          const result = await theoryBank.history(item.id)
                          if (mounted.current) setHistory(result.data)
                        })
                      }
                      className="h-8 border-[#1E2629] bg-[#0F1416] text-[#8B9D9F] hover:text-[#2DD4BF] hover:bg-[#1A2225] text-xs cursor-pointer"
                    >
                      <History className="h-3.5 w-3.5 mr-1.5" />
                      Historial
                    </Button>
                  </div>
                </CardHeader>

                <CardContent className="pt-0 space-y-3">
                  {/* Detalles de Respuesta de Referencia y Rúbrica */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2 border-t border-[#1E2629]/80 text-xs">
                    <div className="rounded-lg bg-[#0F1416] border border-[#1E2629] p-3 space-y-1">
                      <div className="flex items-center justify-between text-[11px] font-semibold text-[#8B9D9F] uppercase">
                        <span>Respuesta de Referencia</span>
                        {hasReference ? (
                          <span className="text-emerald-400">Completa</span>
                        ) : (
                          <span className="text-amber-400">Pendiente</span>
                        )}
                      </div>
                      <p className="text-[#F0FDFA]/90 line-clamp-2">
                        {hasReference
                          ? item.content.reference_answer
                          : "Sin respuesta de referencia cargada. Editá la pregunta para completarla antes de publicar."}
                      </p>
                    </div>

                    <div className="rounded-lg bg-[#0F1416] border border-[#1E2629] p-3 space-y-1.5">
                      <div className="flex items-center justify-between text-[11px] font-semibold text-[#8B9D9F] uppercase">
                        <span>Rúbrica ({item.content.criteria.length} criterios)</span>
                        <span
                          className={
                            isReadyToPublish ? "text-emerald-400 font-bold" : "text-amber-400 font-bold"
                          }
                        >
                          Suma: {weightSum}% / 100%
                        </span>
                      </div>
                      {item.content.criteria.length === 0 ? (
                        <p className="text-[#8B9D9F]">
                          Sin criterios de rúbrica configurados.
                        </p>
                      ) : (
                        <div className="flex flex-wrap gap-1.5">
                          {item.content.criteria.map((c, idx) => (
                            <span
                              key={idx}
                              className="inline-flex items-center gap-1 rounded bg-[#141C1E] border border-[#1E2629] px-2 py-0.5 text-[11px] text-[#F0FDFA]"
                            >
                              <strong className="text-[#2DD4BF]">{c.weight}%</strong> {c.name}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      {/* Paginación */}
      <nav
        aria-label="Paginación"
        className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#1E2629] bg-[#141C1E] px-4 py-3"
      >
        <span className="text-xs font-medium text-[#8B9D9F]">{count} preguntas</span>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={busy || loading || offset === 0}
            onClick={() => setOffset((n) => Math.max(0, n - 20))}
            className="border-[#1E2629] bg-[#0F1416] text-[#F0FDFA] hover:bg-[#1A2225] text-xs"
          >
            Anterior
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={busy || loading || offset + 20 >= count}
            onClick={() => setOffset((n) => n + 20)}
            className="border-[#1E2629] bg-[#0F1416] text-[#F0FDFA] hover:bg-[#1A2225] text-xs"
          >
            Siguiente
          </Button>
        </div>
      </nav>

      {/* Historial Inmutable de Versiones */}
      {history && (
        <section
          aria-label="Historial de versiones"
          className="space-y-4 rounded-2xl border border-[#00786F]/40 bg-[#141C1E] p-5 shadow-lg"
        >
          <div className="flex items-center justify-between border-b border-[#1E2629] pb-3">
            <div className="flex items-center gap-2">
              <History className="h-5 w-5 text-[#2DD4BF]" />
              <h2 className="text-lg font-bold text-[#F0FDFA]">Historial inmutable</h2>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setHistory(null)}
              className="text-xs text-[#8B9D9F] hover:text-[#F0FDFA]"
            >
              Cerrar historial
            </Button>
          </div>

          <div className="grid gap-3">
            {history.map((item) => (
              <Card key={item.version} className="border-[#1E2629] bg-[#0F1416] text-[#F0FDFA]">
                <CardContent className="grid gap-2 py-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold text-[#2DD4BF]">
                      Versión {item.version} · {item.status}
                    </h3>
                    <span className="text-xs text-[#8B9D9F]">
                      {item.content.time_limit_seconds}s · {item.content.max_score} pts
                    </span>
                  </div>
                  <p className="text-sm font-semibold text-[#F0FDFA]">{item.content.prompt}</p>
                  {item.content.reference_answer && (
                    <p className="text-xs text-[#8B9D9F]">{item.content.reference_answer}</p>
                  )}
                  {item.content.criteria.map((criterion, index) => (
                    <p key={index} className="text-xs text-[#F0FDFA]/80">
                      {criterion.name}: {criterion.weight}% — {criterion.description}
                    </p>
                  ))}
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

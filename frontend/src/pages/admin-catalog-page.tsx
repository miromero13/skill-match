import { useEffect, useState, useMemo } from "react"
import { useAdminCatalogStore } from "@/stores/admin-catalog-store"
import type { SkillLevel, RubricCriterion } from "@/types/catalog"
import {
  Sparkles,
  Plus,
  Search,
  FolderPlus,
  Cpu,
  Layers,
  CheckCircle2,
  Clock,
  Trash2,
  Edit3,
  Loader2,
  BookOpen,
  X,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog"

const CANONICAL_LEVELS_DEF = [
  { level_number: 1, name: "Principiante", defaultMinScore: 60 },
  { level_number: 2, name: "Elemental", defaultMinScore: 70 },
  { level_number: 3, name: "Intermedio", defaultMinScore: 75 },
  { level_number: 4, name: "Avanzado", defaultMinScore: 85 },
  { level_number: 5, name: "Master Pedagogo", defaultMinScore: 90 },
]

export function AdminCatalogPage() {
  const {
    categories,
    challengeTypes,
    skills,
    totalSkills,
    selectedCategoryId,
    searchTerm,
    readyFilter,
    isLoading,
    isSubmitting,
    isSkillModalOpen,
    isCategoryModalOpen,
    isChallengeTypeModalOpen,
    editingSkill,
    setSelectedCategoryId,
    setSearchTerm,
    setReadyFilter,
    openCreateSkillModal,
    openEditSkillModal,
    closeSkillModal,
    openCategoryModal,
    closeCategoryModal,
    openChallengeTypeModal,
    closeChallengeTypeModal,
    fetchInitialData,
    createCategory,
    createChallengeType,
    saveSkill,
    toggleReady,
    toggleStatus,
    deleteSkill,
  } = useAdminCatalogStore()

  // Local state for skill form
  const [skillFormCategoryId, setSkillFormCategoryId] = useState("")
  const [skillFormName, setSkillFormName] = useState("")
  const [skillFormChallengeTypeId, setSkillFormChallengeTypeId] = useState("")
  const [skillFormDescription, setSkillFormDescription] = useState("")
  const [skillFormThreshold, setSkillFormThreshold] = useState(80)
  const [skillFormIsReady, setSkillFormIsReady] = useState(false)
  const [skillFormLevels, setSkillFormLevels] = useState<SkillLevel[]>([])
  const [activeLevelTab, setActiveLevelTab] = useState("1")

  // Category in-place form
  const [catName, setCatName] = useState("")
  const [catDescription, setCatDescription] = useState("")

  // Challenge Type in-place form
  const [challengeName, setChallengeName] = useState("")
  const [challengeCode, setChallengeCode] = useState("")
  const [challengeModality, setChallengeModality] = useState("CODE")
  const [challengeDescription, setChallengeDescription] = useState("")

  useEffect(() => {
    fetchInitialData()
  }, [fetchInitialData])

  const handleOpenCreateModal = () => {
    setSkillFormCategoryId(categories[0]?.id || "")
    setSkillFormName("")
    setSkillFormChallengeTypeId(challengeTypes[0]?.id || "")
    setSkillFormDescription("")
    setSkillFormThreshold(80)
    setSkillFormIsReady(false)
    setSkillFormLevels([])
    setActiveLevelTab("1")
    openCreateSkillModal()
  }

  const handleOpenEditModal = (skill: (typeof skills)[number]) => {
    setSkillFormCategoryId(skill.category_id)
    setSkillFormName(skill.name)
    setSkillFormChallengeTypeId(skill.challenge_type_id || "")
    setSkillFormDescription(skill.description || "")
    setSkillFormThreshold(skill.min_approval_threshold)
    setSkillFormIsReady(skill.is_ready_to_publish)

    const existingLevels = (skill.levels || []).map((l) => ({
      level_number: l.level_number,
      name: l.name,
      description: l.description || "",
      rubric: l.rubric
        ? {
            min_score: l.rubric.min_score ?? 70,
            instructions: l.rubric.instructions || "",
            criteria: l.rubric.criteria || [],
          }
        : {
            min_score: 70,
            instructions: "",
            criteria: [],
          },
    }))
    setSkillFormLevels(existingLevels)
    if (existingLevels.length > 0) {
      setActiveLevelTab(String(existingLevels[0].level_number))
    } else {
      setActiveLevelTab("1")
    }
    openEditSkillModal(skill)
  }

  const addManualLevel = () => {
    setSkillFormLevels((prev) => {
      const nextNum = prev.length + 1
      if (nextNum > 5) return prev
      const defaultName = CANONICAL_LEVELS_DEF.find((c) => c.level_number === nextNum)?.name || `Nivel ${nextNum}`
      const newLevel: SkillLevel = {
        level_number: nextNum,
        name: defaultName,
        description: "",
        rubric: {
          min_score: 70,
          instructions: "",
          criteria: [],
        },
      }
      setActiveLevelTab(String(nextNum))
      return [...prev, newLevel]
    })
  }

  const removeManualLevel = (levelNum: number) => {
    setSkillFormLevels((prev) => {
      const filtered = prev.filter((l) => l.level_number !== levelNum)
      // Re-index levels 1..N
      const reindexed = filtered.map((lvl, idx) => ({
        ...lvl,
        level_number: idx + 1,
      }))
      if (reindexed.length > 0) {
        setActiveLevelTab(String(reindexed[0].level_number))
      }
      return reindexed
    })
  }

  const updateLevelName = (levelNum: number, name: string) => {
    setSkillFormLevels((prev) =>
      prev.map((lvl) => (lvl.level_number === levelNum ? { ...lvl, name } : lvl))
    )
  }

  // Filter skills in memory for search & ready filter
  const filteredSkills = useMemo(() => {
    return skills.filter((skill) => {
      if (readyFilter === "ready" && !skill.is_ready_to_publish) return false
      if (readyFilter === "draft" && skill.is_ready_to_publish) return false
      if (searchTerm) {
        const term = searchTerm.toLowerCase()
        return (
          skill.name.toLowerCase().includes(term) ||
          skill.slug.toLowerCase().includes(term) ||
          (skill.description && skill.description.toLowerCase().includes(term))
        )
      }
      return true
    })
  }, [skills, readyFilter, searchTerm])

  const handleSaveSkill = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!skillFormCategoryId || !skillFormName.trim()) return

    const payload = {
      category_id: skillFormCategoryId,
      name: skillFormName.trim(),
      challenge_type_id: skillFormChallengeTypeId || null,
      description: skillFormDescription.trim() || undefined,
      min_approval_threshold: Number(skillFormThreshold),
      is_ready_to_publish: skillFormIsReady,
      levels: skillFormLevels,
    }

    await saveSkill(payload, editingSkill ? editingSkill.id : undefined)
  }

  const handleCreateCategory = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!catName.trim()) return
    const created = await createCategory({
      name: catName.trim(),
      description: catDescription.trim() || undefined,
    })
    if (created) {
      setCatName("")
      setCatDescription("")
      setSkillFormCategoryId(created.id)
    }
  }

  const handleCreateChallengeType = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!challengeName.trim() || !challengeCode.trim()) return
    const created = await createChallengeType({
      name: challengeName.trim(),
      code: challengeCode.trim(),
      evaluation_modality: challengeModality,
      description: challengeDescription.trim() || undefined,
    })
    if (created) {
      setChallengeName("")
      setChallengeCode("")
      setChallengeDescription("")
      setSkillFormChallengeTypeId(created.id)
    }
  }

  const updateLevelRubric = (
    levelNum: number,
    field: "instructions" | "min_score",
    value: string | number
  ) => {
    setSkillFormLevels((prev) =>
      prev.map((lvl) => {
        if (lvl.level_number !== levelNum) return lvl
        const rubric = lvl.rubric || { min_score: 70, instructions: "", criteria: [] }
        return {
          ...lvl,
          rubric: {
            ...rubric,
            [field]: value,
          },
        }
      })
    )
  }

  const addCriterion = (levelNum: number) => {
    setSkillFormLevels((prev) =>
      prev.map((lvl) => {
        if (lvl.level_number !== levelNum) return lvl
        const rubric = lvl.rubric || { min_score: 70, instructions: "", criteria: [] }
        const newCriterion: RubricCriterion = {
          name: "Nuevo Criterio",
          weight: 20,
          description: "Descripción de evaluación",
        }
        return {
          ...lvl,
          rubric: {
            ...rubric,
            criteria: [...rubric.criteria, newCriterion],
          },
        }
      })
    )
  }

  const updateCriterion = (
    levelNum: number,
    critIndex: number,
    field: keyof RubricCriterion,
    val: string | number
  ) => {
    setSkillFormLevels((prev) =>
      prev.map((lvl) => {
        if (lvl.level_number !== levelNum || !lvl.rubric) return lvl
        const criteria = [...lvl.rubric.criteria]
        criteria[critIndex] = { ...criteria[critIndex], [field]: val }
        return {
          ...lvl,
          rubric: { ...lvl.rubric, criteria },
        }
      })
    )
  }

  const removeCriterion = (levelNum: number, critIndex: number) => {
    setSkillFormLevels((prev) =>
      prev.map((lvl) => {
        if (lvl.level_number !== levelNum || !lvl.rubric) return lvl
        const criteria = lvl.rubric.criteria.filter((_, i) => i !== critIndex)
        return {
          ...lvl,
          rubric: { ...lvl.rubric, criteria },
        }
      })
    )
  }

  return (
    <div className="p-4 md:p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#1E2629] pb-6">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2.5 bg-[#00786F]/20 text-[#2DD4BF] border border-[#00786F]/40 rounded-xl">
              <Sparkles className="h-6 w-6" />
            </div>
            <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-[#F0FDFA]">
              Catálogo de Habilidades
            </h1>
          </div>
          <p className="text-sm text-[#8B9D9F] mt-1.5 max-w-2xl leading-relaxed">
            Organiza las disciplinas por categoría, configura la escalera canónica de 5 niveles con rúbricas de IA y marca las habilidades listas para producción.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <Button
            variant="outline"
            size="sm"
            onClick={openCategoryModal}
            className="border-[#1E2629] bg-[#141C1E] text-[#F0FDFA] hover:bg-[#1A2225] hover:border-[#00786F]/50 flex items-center gap-1.5 cursor-pointer shadow-xs"
          >
            <FolderPlus className="h-4 w-4 text-[#8B9D9F]" />
            <span>+ Categoría</span>
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={openChallengeTypeModal}
            className="border-[#1E2629] bg-[#141C1E] text-[#F0FDFA] hover:bg-[#1A2225] hover:border-[#00786F]/50 flex items-center gap-1.5 cursor-pointer shadow-xs"
          >
            <Cpu className="h-4 w-4 text-[#8B9D9F]" />
            <span>+ Tipo Desafío IA</span>
          </Button>
          <Button
            onClick={handleOpenCreateModal}
            className="bg-[#00786F] hover:bg-[#00665E] text-[#F0FDFA] font-bold flex items-center gap-1.5 cursor-pointer shadow-xs"
          >
            <Plus className="h-4 w-4" />
            <span>Nueva Habilidad</span>
          </Button>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between bg-[#141C1E] p-4 rounded-xl border border-[#1E2629] shadow-sm">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-[#8B9D9F]" />
          <Input
            placeholder="Buscar por habilidad o descripción..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-9 bg-[#0F1416] border-[#1E2629] text-[#F0FDFA] placeholder:text-[#67787C] focus-visible:border-[#00786F]"
          />
        </div>

        {/* Category Filter Pills / Dropdown */}
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant={selectedCategoryId === null ? "default" : "outline"}
            size="sm"
            onClick={() => setSelectedCategoryId(null)}
            className={
              selectedCategoryId === null
                ? "bg-[#00786F] hover:bg-[#00665E] text-white font-bold shadow-xs cursor-pointer"
                : "border-[#1E2629] bg-[#0F1416] text-[#8B9D9F] hover:text-[#F0FDFA] hover:bg-[#1A2225] cursor-pointer"
            }
          >
            Todas ({totalSkills})
          </Button>
          {categories.map((cat) => (
            <Button
              key={cat.id}
              variant={selectedCategoryId === cat.id ? "default" : "outline"}
              size="sm"
              onClick={() => setSelectedCategoryId(cat.id)}
              className={
                selectedCategoryId === cat.id
                  ? "bg-[#00786F] hover:bg-[#00665E] text-white font-bold shadow-xs cursor-pointer"
                  : "border-[#1E2629] bg-[#0F1416] text-[#8B9D9F] hover:text-[#F0FDFA] hover:bg-[#1A2225] cursor-pointer"
              }
            >
              {cat.name}
            </Button>
          ))}
        </div>

        {/* Ready status filter */}
        <div className="flex items-center gap-1 bg-[#0F1416] border border-[#1E2629] p-1 rounded-lg">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setReadyFilter("all")}
            className={
              readyFilter === "all"
                ? "h-7 text-xs font-bold bg-[#1A2225] text-[#F0FDFA]"
                : "h-7 text-xs font-medium text-[#8B9D9F] hover:text-[#F0FDFA]"
            }
          >
            Todas
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setReadyFilter("ready")}
            className={
              readyFilter === "ready"
                ? "h-7 text-xs font-bold bg-[#00786F] hover:bg-[#00665E] text-white"
                : "h-7 text-xs font-medium text-[#8B9D9F] hover:text-[#F0FDFA]"
            }
          >
            Listas
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setReadyFilter("draft")}
            className={
              readyFilter === "draft"
                ? "h-7 text-xs font-bold bg-amber-600 hover:bg-amber-700 text-white"
                : "h-7 text-xs font-medium text-[#8B9D9F] hover:text-[#F0FDFA]"
            }
          >
            En preparación
          </Button>
        </div>
      </div>

      {/* Skills Grid / Table */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center p-16 text-[#8B9D9F]">
          <Loader2 className="h-8 w-8 animate-spin text-[#00786F] mb-2" />
          <p className="text-sm">Cargando catálogo de habilidades...</p>
        </div>
      ) : filteredSkills.length === 0 ? (
        <div className="flex flex-col items-center justify-center p-16 text-center border border-dashed border-[#1E2629] rounded-2xl bg-[#141C1E]">
          <BookOpen className="h-12 w-12 text-[#8B9D9F]/50 mb-3" />
          <h3 className="text-lg font-bold text-[#F0FDFA]">No se encontraron habilidades</h3>
          <p className="text-sm text-[#8B9D9F] max-w-sm mt-1">
            {searchTerm || selectedCategoryId || readyFilter !== "all"
              ? "Prueba cambiando los filtros de búsqueda o categoría."
              : "Comienza creando tu primera habilidad haciendo clic en 'Nueva Habilidad'."}
          </p>
          <Button onClick={handleOpenCreateModal} className="mt-4 bg-[#00786F] hover:bg-[#00665E] text-[#F0FDFA] font-bold">
            <Plus className="h-4 w-4 mr-1.5" />
            Crear Habilidad
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {filteredSkills.map((skill) => {
            const category = categories.find((c) => c.id === skill.category_id)
            const challenge = challengeTypes.find((ct) => ct.id === skill.challenge_type_id)

            return (
              <Card
                key={skill.id}
                className="bg-[#141C1E] border-[#1E2629] hover:border-[#00786F]/50 transition-all shadow-sm rounded-xl text-[#F0FDFA]"
              >
                <CardContent className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
                  {/* Info Column */}
                  <div className="space-y-2 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-lg font-bold text-[#F0FDFA]">{skill.name}</span>
                      <Badge className="bg-[#1A2225] text-[#8B9D9F] border-[#1E2629] text-xs font-normal">
                        {category?.name || "Sin categoría"}
                      </Badge>
                      {challenge && (
                        <Badge className="bg-indigo-500/15 text-indigo-300 border-indigo-500/30 text-xs">
                          <Cpu className="h-3 w-3 mr-1 text-indigo-400" />
                          {challenge.name} ({challenge.evaluation_modality})
                        </Badge>
                      )}
                      <Badge className="bg-[#00786F]/15 text-[#2DD4BF] border-[#00786F]/30 text-xs font-semibold">
                        Umbral: {skill.min_approval_threshold}%
                      </Badge>
                    </div>

                    {skill.description && (
                      <p className="text-xs text-[#8B9D9F] line-clamp-1">{skill.description}</p>
                    )}

                    {/* Canonical Levels ladder mini-progress */}
                    <div className="flex items-center gap-1.5 pt-1">
                      <span className="text-xs text-[#8B9D9F] mr-1 flex items-center gap-1">
                        <Layers className="h-3 w-3 text-[#67787C]" />
                        Escalera:
                      </span>
                      {CANONICAL_LEVELS_DEF.map((lvl) => {
                        const levelData = skill.levels?.find((l) => l.level_number === lvl.level_number)
                        const hasRubric = (levelData?.rubric?.criteria?.length || 0) > 0

                        return (
                          <div
                            key={lvl.level_number}
                            title={`Nivel ${lvl.level_number}: ${lvl.name} (${hasRubric ? "Rúbrica configurada" : "Sin criterios"})`}
                            className={`flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full border transition-colors ${
                              hasRubric
                                ? "bg-[#00786F]/20 text-[#2DD4BF] border-[#00786F]/40"
                                : "bg-[#0F1416] text-[#67787C] border-[#1E2629]"
                            }`}
                          >
                            <span className="font-semibold">{lvl.level_number}</span>
                            <span className="hidden sm:inline">{lvl.name}</span>
                          </div>
                        )
                      })}
                    </div>
                  </div>

                  {/* Status and Action Column */}
                  <div className="flex flex-wrap items-center gap-3 border-t border-[#1E2629] md:border-t-0 pt-3 md:pt-0">
                    {/* Ready to publish badge/toggle */}
                    <div className="flex items-center gap-2 bg-[#0F1416] px-3 py-1.5 rounded-lg border border-[#1E2629]">
                      <span className="text-xs font-medium text-[#8B9D9F]">¿Lista para publicar?</span>
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => toggleReady(skill.id, skill.is_ready_to_publish)}
                        className={`h-7 text-xs px-2.5 rounded-full font-semibold transition-colors cursor-pointer ${
                          skill.is_ready_to_publish
                            ? "bg-[#00786F] hover:bg-[#00665E] text-white"
                            : "bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border border-amber-500/40"
                        }`}
                      >
                        {skill.is_ready_to_publish ? (
                          <>
                            <CheckCircle2 className="h-3.5 w-3.5 mr-1 text-white" />
                            <span>Lista</span>
                          </>
                        ) : (
                          <>
                            <Clock className="h-3.5 w-3.5 mr-1" />
                            <span>En preparación</span>
                          </>
                        )}
                      </Button>
                    </div>

                    {/* Public Active Switch */}
                    <div className="flex items-center gap-2">
                      <Switch
                        checked={skill.is_active}
                        onCheckedChange={() => toggleStatus(skill.id, skill.is_active)}
                        id={`status-${skill.id}`}
                      />
                      <Label
                        htmlFor={`status-${skill.id}`}
                        className={`text-xs font-medium cursor-pointer ${
                          skill.is_active ? "text-[#2DD4BF] font-bold" : "text-[#8B9D9F]"
                        }`}
                      >
                        {skill.is_active ? "Publicada" : "Inactiva"}
                      </Label>
                    </div>

                    {/* Edit and Delete Buttons */}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleOpenEditModal(skill)}
                      className="border-[#1E2629] bg-[#0F1416] text-[#F0FDFA] hover:bg-[#1A2225] hover:border-[#00786F]/50 flex items-center gap-1.5 cursor-pointer shadow-xs"
                    >
                      <Edit3 className="h-3.5 w-3.5 text-[#8B9D9F]" />
                      <span>Editar y Rúbricas</span>
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => {
                        if (confirm(`¿Estás seguro de eliminar la habilidad "${skill.name}"?`)) {
                          deleteSkill(skill.id)
                        }
                      }}
                      className="text-[#8B9D9F] hover:text-red-400 hover:bg-red-500/10 h-8 w-8 cursor-pointer"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      {/* SKILL MODAL: Extra amplio (max-w-[1360px] / w-[96vw]), limpio, 2 columnas con componentes Shadcn */}
      <Dialog open={isSkillModalOpen} onOpenChange={(open) => !open && closeSkillModal()}>
        <DialogContent
          className="w-[96vw] max-w-[1360px] p-0 border border-[#1E2629] bg-[#141C1E] text-[#F0FDFA] rounded-2xl shadow-2xl overflow-hidden focus:outline-none"
          style={{ width: "96vw", maxWidth: "1360px", maxHeight: "90vh" }}
          showCloseButton={false}
        >
          <div className="flex flex-col h-full max-h-[90vh]">
            {/* Header conciso */}
            <DialogHeader className="px-6 py-4 border-b border-[#1E2629] flex flex-row items-center justify-between shrink-0 bg-[#141C1E] space-y-0">
              <div className="flex items-center gap-3">
                <span className="w-2.5 h-2.5 rounded-full bg-[#00786F]" />
                <DialogTitle className="text-base font-bold text-[#F0FDFA] uppercase tracking-tight">
                  {editingSkill ? `Editar Habilidad: ${editingSkill.name}` : "Nueva Habilidad Técnica"}
                </DialogTitle>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={closeSkillModal}
                className="h-8 w-8 text-[#8B9D9F] hover:text-[#F0FDFA] hover:bg-[#1A2225] cursor-pointer"
                title="Cerrar modal"
              >
                <X className="h-4 w-4" />
              </Button>
            </DialogHeader>

            {/* Formulario en Grid 2 columnas: Columna izquierda Configuración General, Columna derecha Niveles */}
            <form onSubmit={handleSaveSkill} className="flex-1 overflow-y-auto p-6 sm:p-8 flex flex-col gap-6">
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
                {/* Columna Izquierda: Información Básica de la Habilidad (lg:col-span-4) */}
                <Card className="lg:col-span-4 bg-[#0F1416] border-[#1E2629]">
                  <CardHeader className="pb-3 border-b border-[#1E2629]">
                    <CardTitle className="text-xs font-bold text-[#F0FDFA] uppercase tracking-wider">
                      Configuración General
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4 pt-4">
                    {/* Categoría */}
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <Label htmlFor="modal-category" className="text-xs font-semibold text-[#8B9D9F] uppercase tracking-wider">
                          Categoría *
                        </Label>
                        <Button
                          type="button"
                          variant="link"
                          size="sm"
                          onClick={openCategoryModal}
                          className="h-auto p-0 text-xs font-semibold text-[#2DD4BF] hover:text-[#2DD4BF]/80"
                        >
                          + Nueva
                        </Button>
                      </div>
                      <Select
                        value={skillFormCategoryId}
                        onValueChange={setSkillFormCategoryId}
                        required
                      >
                        <SelectTrigger id="modal-category" className="w-full bg-[#141C1E] border-[#1E2629] text-[#F0FDFA]">
                          <SelectValue placeholder="Seleccionar categoría..." />
                        </SelectTrigger>
                        <SelectContent className="bg-[#141C1E] border-[#1E2629] text-[#F0FDFA]">
                          {categories.map((c) => (
                            <SelectItem key={c.id} value={c.id}>
                              {c.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    {/* Nombre de la Habilidad */}
                    <div className="space-y-1.5">
                      <Label htmlFor="modal-skill-name" className="text-xs font-semibold text-[#8B9D9F] uppercase tracking-wider">
                        Nombre de la Habilidad *
                      </Label>
                      <Input
                        id="modal-skill-name"
                        type="text"
                        placeholder="Ej. Python Backend & Algoritmos"
                        value={skillFormName}
                        onChange={(e) => setSkillFormName(e.target.value)}
                        required
                        className="bg-[#141C1E] border-[#1E2629] text-[#F0FDFA] placeholder:text-[#67787C]"
                      />
                    </div>

                    {/* Tipo de Desafío IA */}
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <Label htmlFor="modal-challenge-type" className="text-xs font-semibold text-[#8B9D9F] uppercase tracking-wider">
                          Tipo de Desafío IA:
                        </Label>
                        <Button
                          type="button"
                          variant="link"
                          size="sm"
                          onClick={openChallengeTypeModal}
                          className="h-auto p-0 text-xs font-semibold text-[#2DD4BF] hover:text-[#2DD4BF]/80"
                        >
                          + Nuevo
                        </Button>
                      </div>
                      <Select
                        value={skillFormChallengeTypeId || "none"}
                        onValueChange={(val) => setSkillFormChallengeTypeId(val === "none" ? "" : val)}
                      >
                        <SelectTrigger id="modal-challenge-type" className="w-full bg-[#141C1E] border-[#1E2629] text-[#F0FDFA]">
                          <SelectValue placeholder="Sin evaluación de IA asignada" />
                        </SelectTrigger>
                        <SelectContent className="bg-[#141C1E] border-[#1E2629] text-[#F0FDFA]">
                          <SelectItem value="none">Sin evaluación de IA asignada</SelectItem>
                          {challengeTypes.map((ct) => (
                            <SelectItem key={ct.id} value={ct.id}>
                              {ct.name} ({ct.evaluation_modality})
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    {/* Umbral de Aprobación */}
                    <div className="space-y-1.5">
                      <Label htmlFor="modal-threshold" className="text-xs font-semibold text-[#8B9D9F] uppercase tracking-wider">
                        Umbral Mínimo de Aprobación:
                      </Label>
                      <Select
                        value={String(skillFormThreshold)}
                        onValueChange={(val) => setSkillFormThreshold(Number(val))}
                      >
                        <SelectTrigger id="modal-threshold" className="w-full bg-[#141C1E] border-[#1E2629] text-[#F0FDFA]">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-[#141C1E] border-[#1E2629] text-[#F0FDFA]">
                          <SelectItem value="60">60% de aprobación</SelectItem>
                          <SelectItem value="70">70% de aprobación</SelectItem>
                          <SelectItem value="75">75% de aprobación</SelectItem>
                          <SelectItem value="80">80% de aprobación</SelectItem>
                          <SelectItem value="85">85% de aprobación</SelectItem>
                          <SelectItem value="90">90% de aprobación</SelectItem>
                          <SelectItem value="95">95% de aprobación</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    {/* Toggle Publicar */}
                    <div className="flex items-center justify-between pt-3 border-t border-[#1E2629]">
                      <Label htmlFor="modal-ready-toggle" className="text-xs font-medium text-[#F0FDFA] cursor-pointer">
                        Habilidad lista para publicar
                      </Label>
                      <Switch
                        id="modal-ready-toggle"
                        checked={skillFormIsReady}
                        onCheckedChange={setSkillFormIsReady}
                      />
                    </div>
                  </CardContent>
                </Card>

                {/* Columna Derecha: Niveles y Rúbricas (lg:col-span-8) */}
                <Card className="lg:col-span-8 border-[#1E2629] bg-[#0F1416] shadow-xs overflow-hidden">
                  <div className="bg-[#141C1E] px-5 py-3 border-b border-[#1E2629] flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-bold text-[#F0FDFA] uppercase tracking-wider">
                        Niveles ({skillFormLevels.length}/5)
                      </span>
                      {skillFormLevels.length > 0 && (
                        <div className="flex items-center gap-1.5">
                          {skillFormLevels.map((lvl) => (
                            <Button
                              key={lvl.level_number}
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => setActiveLevelTab(String(lvl.level_number))}
                              className={`h-7 px-3 text-xs font-semibold cursor-pointer ${
                                activeLevelTab === String(lvl.level_number)
                                  ? "bg-[#00786F] hover:bg-[#00665E] text-white border-[#00786F]"
                                  : "border-[#1E2629] bg-[#0F1416] text-[#8B9D9F] hover:text-[#F0FDFA] hover:bg-[#1A2225]"
                              }`}
                            >
                              Nivel {lvl.level_number}
                            </Button>
                          ))}
                        </div>
                      )}
                    </div>

                    {skillFormLevels.length < 5 && (
                      <Button
                        type="button"
                        size="sm"
                        onClick={addManualLevel}
                        className="h-7 px-3 bg-[#00786F] hover:bg-[#00665E] text-white text-xs font-semibold gap-1.5 cursor-pointer"
                      >
                        <Plus className="h-3.5 w-3.5" />
                        Agregar Nivel
                      </Button>
                    )}
                  </div>

                  <CardContent className="p-5">
                    {skillFormLevels.length === 0 ? (
                      <div className="p-12 text-center flex flex-col items-center justify-center gap-3 text-[#8B9D9F]">
                        <p className="text-sm font-medium">No hay niveles configurados para esta habilidad.</p>
                        <Button
                          type="button"
                          onClick={addManualLevel}
                          className="bg-[#00786F] hover:bg-[#00665E] text-white text-xs font-semibold cursor-pointer"
                        >
                          <Plus className="h-3.5 w-3.5 mr-1.5" />
                          Agregar Nivel 1
                        </Button>
                      </div>
                    ) : (
                      skillFormLevels
                        .filter((lvl) => String(lvl.level_number) === activeLevelTab)
                        .map((lvl) => (
                          <div key={lvl.level_number} className="flex flex-col gap-4">
                            {/* Datos del nivel activo */}
                            <div className="grid grid-cols-1 sm:grid-cols-12 gap-3 bg-[#141C1E] p-4 rounded-xl border border-[#1E2629] items-end">
                              <div className="sm:col-span-7 space-y-1.5">
                                <Label htmlFor={`level-name-${lvl.level_number}`} className="text-xs font-semibold text-[#8B9D9F] uppercase tracking-wider">
                                  Nombre del Nivel {lvl.level_number}:
                                </Label>
                                <Input
                                  id={`level-name-${lvl.level_number}`}
                                  type="text"
                                  value={lvl.name}
                                  onChange={(e) => updateLevelName(lvl.level_number, e.target.value)}
                                  placeholder="Ej. Principiante, Intermedio, Avanzado..."
                                  required
                                  className="bg-[#0F1416] border-[#1E2629] text-[#F0FDFA]"
                                />
                              </div>

                              <div className="sm:col-span-3 space-y-1.5">
                                <Label htmlFor={`min-score-${lvl.level_number}`} className="text-xs font-semibold text-[#8B9D9F] uppercase tracking-wider">
                                  Puntaje Mínimo (0-100):
                                </Label>
                                <Input
                                  id={`min-score-${lvl.level_number}`}
                                  type="number"
                                  min={0}
                                  max={100}
                                  value={lvl.rubric?.min_score ?? 70}
                                  onChange={(e) => updateLevelRubric(lvl.level_number, "min_score", Number(e.target.value))}
                                  className="bg-[#0F1416] border-[#1E2629] font-bold text-[#2DD4BF]"
                                />
                              </div>

                              <div className="sm:col-span-2">
                                <Button
                                  type="button"
                                  variant="outline"
                                  size="sm"
                                  onClick={() => removeManualLevel(lvl.level_number)}
                                  className="w-full text-red-400 border-red-500/30 bg-[#0F1416] hover:bg-red-500/10 text-xs font-semibold cursor-pointer"
                                >
                                  Eliminar
                                </Button>
                              </div>
                            </div>

                            {/* Criterios del nivel */}
                            <div className="space-y-3">
                              <div className="flex items-center justify-between">
                                <Label className="text-xs font-semibold text-[#8B9D9F] uppercase tracking-wider">
                                  Criterios de Evaluación ({lvl.rubric?.criteria?.length || 0})
                                </Label>
                                <Button
                                  type="button"
                                  variant="link"
                                  size="sm"
                                  onClick={() => addCriterion(lvl.level_number)}
                                  className="h-auto p-0 text-xs font-semibold text-[#2DD4BF] hover:text-[#2DD4BF]/80"
                                >
                                  + Agregar Criterio
                                </Button>
                              </div>

                              {lvl.rubric?.criteria?.length === 0 ? (
                                <div className="p-4 text-center text-xs text-[#8B9D9F] bg-[#141C1E] rounded-lg border border-dashed border-[#1E2629]">
                                  Sin criterios configurados. Haz clic en "+ Agregar Criterio".
                                </div>
                              ) : (
                                <div className="space-y-2">
                                  {lvl.rubric?.criteria.map((crit, cIdx) => (
                                    <div
                                      key={cIdx}
                                      className="flex items-center gap-3 p-2.5 rounded-lg bg-[#141C1E] border border-[#1E2629]"
                                    >
                                      <Input
                                        type="text"
                                        placeholder="Nombre del criterio de evaluación"
                                        value={crit.name}
                                        onChange={(e) => updateCriterion(lvl.level_number, cIdx, "name", e.target.value)}
                                        className="h-8 flex-1 min-w-0 bg-[#0F1416] border-[#1E2629] text-[#F0FDFA] text-xs"
                                      />
                                      <div className="flex items-center gap-1.5 shrink-0">
                                        <Input
                                          type="number"
                                          min={0}
                                          max={100}
                                          value={crit.weight}
                                          onChange={(e) => updateCriterion(lvl.level_number, cIdx, "weight", Number(e.target.value))}
                                          className="h-8 w-16 text-center bg-[#0F1416] border-[#1E2629] text-[#2DD4BF] text-xs font-bold"
                                        />
                                        <span className="text-xs text-[#8B9D9F] font-bold">%</span>
                                      </div>
                                      <Button
                                        type="button"
                                        variant="ghost"
                                        size="icon"
                                        onClick={() => removeCriterion(lvl.level_number, cIdx)}
                                        className="h-8 w-8 text-[#8B9D9F] hover:text-red-400 hover:bg-red-500/10 cursor-pointer"
                                        title="Eliminar criterio"
                                      >
                                        <X className="h-4 w-4" />
                                      </Button>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                        ))
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* Botones de acción en el pie */}
              <DialogFooter className="px-6 py-4 border-t border-[#1E2629] bg-[#141C1E] flex items-center justify-end gap-3 shrink-0">
                <Button
                  type="button"
                  variant="outline"
                  onClick={closeSkillModal}
                  disabled={isSubmitting}
                  className="border-[#1E2629] bg-[#0F1416] text-[#F0FDFA] hover:bg-[#1A2225] cursor-pointer"
                >
                  Cancelar
                </Button>

                <Button
                  type="submit"
                  disabled={isSubmitting || !skillFormCategoryId || !skillFormName.trim()}
                  className="bg-[#00786F] hover:bg-[#00665E] text-white font-bold cursor-pointer"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin mr-1.5" />
                      <span>Guardando...</span>
                    </>
                  ) : (
                    <span>{editingSkill ? "Actualizar Habilidad ✓" : "Crear Habilidad ✓"}</span>
                  )}
                </Button>
              </DialogFooter>
            </form>
          </div>
        </DialogContent>
      </Dialog>

      {/* CATEGORY IN-PLACE CREATION DIALOG */}
      <Dialog open={isCategoryModalOpen} onOpenChange={(open) => !open && closeCategoryModal()}>
        <DialogContent className="max-w-md bg-[#141C1E] border border-[#1E2629] text-[#F0FDFA]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-[#F0FDFA]">
              <FolderPlus className="h-5 w-5 text-[#2DD4BF]" />
              Nueva Categoría
            </DialogTitle>
            <DialogDescription className="text-[#8B9D9F]">
              Crea una categoría superior para agrupar habilidades (ej. Música, Programación, Idiomas).
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleCreateCategory} className="space-y-4 pt-2">
            <div className="space-y-1.5">
              <Label htmlFor="cat-name" className="text-xs font-semibold text-[#8B9D9F]">
                Nombre de Categoría *
              </Label>
              <Input
                id="cat-name"
                placeholder="Ej: Música, Deportes, Programación..."
                value={catName}
                onChange={(e) => setCatName(e.target.value)}
                required
                className="bg-[#0F1416] border-[#1E2629] text-[#F0FDFA] placeholder:text-[#67787C]"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="cat-desc" className="text-xs font-semibold text-[#8B9D9F]">
                Descripción (opcional)
              </Label>
              <Textarea
                id="cat-desc"
                placeholder="Breve reseña de la categoría..."
                rows={2}
                value={catDescription}
                onChange={(e) => setCatDescription(e.target.value)}
                className="bg-[#0F1416] border-[#1E2629] text-[#F0FDFA] placeholder:text-[#67787C]"
              />
            </div>

            <DialogFooter className="pt-2">
              <Button type="button" variant="outline" onClick={closeCategoryModal} className="border-[#1E2629] bg-[#0F1416] text-[#F0FDFA] hover:bg-[#1A2225] cursor-pointer">
                Cancelar
              </Button>
              <Button type="submit" disabled={isSubmitting} className="bg-[#00786F] hover:bg-[#00665E] text-white font-bold cursor-pointer">
                Crear Categoría
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* CHALLENGE TYPE IN-PLACE CREATION DIALOG */}
      <Dialog open={isChallengeTypeModalOpen} onOpenChange={(open) => !open && closeChallengeTypeModal()}>
        <DialogContent className="max-w-md bg-[#141C1E] border border-[#1E2629] text-[#F0FDFA]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-[#F0FDFA]">
              <Cpu className="h-5 w-5 text-indigo-400" />
              Nuevo Tipo de Desafío IA
            </DialogTitle>
            <DialogDescription className="text-[#8B9D9F]">
              Registra un motor o pipeline de evaluación automatizada propio de SkillMatch.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleCreateChallengeType} className="space-y-4 pt-2">
            <div className="space-y-1.5">
              <Label htmlFor="chal-name" className="text-xs font-semibold text-[#8B9D9F]">
                Nombre del Desafío *
              </Label>
              <Input
                id="chal-name"
                placeholder="Ej: Docker Sandbox + Pytest, Espectro Audio Librosa..."
                value={challengeName}
                onChange={(e) => setChallengeName(e.target.value)}
                required
                className="bg-[#0F1416] border-[#1E2629] text-[#F0FDFA] placeholder:text-[#67787C]"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="chal-code" className="text-xs font-semibold text-[#8B9D9F]">
                  Código Único *
                </Label>
                <Input
                  id="chal-code"
                  placeholder="CODE_SANDBOX"
                  value={challengeCode}
                  onChange={(e) => setChallengeCode(e.target.value.toUpperCase())}
                  required
                  className="bg-[#0F1416] border-[#1E2629] text-[#F0FDFA] placeholder:text-[#67787C]"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="chal-modality" className="text-xs font-semibold text-[#8B9D9F]">
                  Modalidad *
                </Label>
                <Select
                  value={challengeModality}
                  onValueChange={setChallengeModality}
                >
                  <SelectTrigger id="chal-modality" className="w-full bg-[#0F1416] border-[#1E2629] text-[#F0FDFA]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-[#141C1E] border-[#1E2629] text-[#F0FDFA]">
                    <SelectItem value="CODE">Código (Sandbox)</SelectItem>
                    <SelectItem value="AUDIO">Audio (Librosa/PyTorch)</SelectItem>
                    <SelectItem value="VIDEO_POSE">Visión / Pose (OpenCV)</SelectItem>
                    <SelectItem value="THEORY">Teórico / Quiz</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="chal-desc" className="text-xs font-semibold text-[#8B9D9F]">
                Descripción
              </Label>
              <Textarea
                id="chal-desc"
                placeholder="Detalla cómo evalúa este pipeline..."
                rows={2}
                value={challengeDescription}
                onChange={(e) => setChallengeDescription(e.target.value)}
                className="bg-[#0F1416] border-[#1E2629] text-[#F0FDFA] placeholder:text-[#67787C]"
              />
            </div>

            <DialogFooter className="pt-2">
              <Button type="button" variant="outline" onClick={closeChallengeTypeModal} className="border-[#1E2629] bg-[#0F1416] text-[#F0FDFA] hover:bg-[#1A2225] cursor-pointer">
                Cancelar
              </Button>
              <Button type="submit" disabled={isSubmitting} className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold cursor-pointer">
                Crear Tipo IA
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}

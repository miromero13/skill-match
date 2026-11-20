import { useEffect, useMemo, useRef, useState } from "react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Video,
  Mic,
  Code,
  UploadCloud,
  Play,
  Square,
  Trash2,
  Eye,
  ShieldCheck,
  Hash,
  Cpu,
  RefreshCw,
  FileCheck,
  CheckCircle2,
  AlertCircle,
  FileCode,
  Sparkles,
  ChevronDown,
  SlidersHorizontal,
} from "lucide-react"
import { useDatasetCaptureStore } from "@/stores/dataset-capture-store"
import {
  FootballValidationWizard,
  FootballTrainingStudio,
  JugglingVideoAnalyzer,
} from "@/features/football-validation"
import { getSkills, getCategories } from "@/services/admin-catalog-service"
import {
  calculateFileSha256,
  uploadDatasetSample,
  getDatasetSamplePreviewUrl,
} from "@/services/dataset-sample-service"
import type { Skill, Category } from "@/types/catalog"

interface BatchFileItem {
  id: string
  file: File
  name: string
  size: number
  format: string
  sha256?: string
  status: "idle" | "hashing" | "uploading" | "done" | "error"
  errorMessage?: string
}

const CANONICAL_CATEGORIES = [
  { slug: "musica", name: "Música", icon: "🎵", description: "Audio espectral y técnica armónica" },
  { slug: "deporte", name: "Deporte", icon: "⚽", description: "Visión artificial y control de balón" },
  { slug: "programacion", name: "Programación", icon: "💻", description: "AST y patrones algorítmicos" },
]

export function AdminDatasetCapturePage() {
  const {
    isRecording,
    recordingDurationSeconds,
    recordingMode,
    recordedBlob,
    recordedFileName,
    recordedFileHash,
    mediaStream,
    discipline,
    challenge,
    hardwareInfo,
    signedConsent,
    codeContent,
    participantId,
    levelLabel,
    manualTouchCount,
    noiseLevel,
    surface,
    split,
    samples,
    totalCount,
    isLoading,
    isUploading,
    error,
    lastUploadMessage,
    clearLastUploadMessage,
    setRecordingMode,
    setDiscipline,
    setChallenge,
    setHardwareInfo,
    setSignedConsent,
    setCodeContent,
    setParticipantId,
    setLevelLabel,
    setManualTouchCount,
    setNoiseLevel,
    setSurface,
    setSplit,
    setMediaStream,
    setRecordedBlob,
    setRecordingDurationSeconds,
    setIsRecording,
    resetRecording,
    fetchSamples,
    uploadCurrentCapture,
    deleteSampleById,
  } = useDatasetCaptureStore()

  const videoPreviewRef = useRef<HTMLVideoElement>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const timerIntervalRef = useRef<number | null>(null)
  const chunksRef = useRef<Blob[]>([])

  const [filterDiscipline, setFilterDiscipline] = useState<string>("all")
  const [categories, setCategories] = useState<Category[]>([])
  const [activeCategorySlug, setActiveCategorySlug] = useState<string>("deporte")
  const [previewSample, setPreviewSample] = useState<{
    url: string
    format: string
  } | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [loadingPreviewId, setLoadingPreviewId] = useState<string | null>(null)

  const handlePreviewSample = async (sampleId: string) => {
    setLoadingPreviewId(sampleId)
    setPreviewError(null)
    try {
      const res = await getDatasetSamplePreviewUrl(sampleId)
      if (res.statuscode === 200 && res.data) {
        setPreviewSample({ url: res.data.preview_url, format: res.data.file_format })
      } else {
        setPreviewError(res.message)
      }
    } catch (err: unknown) {
      setPreviewError(
        err instanceof Error ? err.message : "No se pudo generar la vista previa."
      )
    } finally {
      setLoadingPreviewId(null)
    }
  }
  const [catalogSkills, setCatalogSkills] = useState<Skill[]>([])
  const [selectedSkillId, setSelectedSkillId] = useState<string>("")
  const [selectedSkillName, setSelectedSkillName] = useState<string>("Dominadas y Control de Balón")
  const [batchFiles, setBatchFiles] = useState<BatchFileItem[]>([])
  const [batchProgress, setBatchProgress] = useState<{ current: number; total: number; filename: string } | null>(null)
  const [batchSplitMode, setBatchSplitMode] = useState<"auto" | "train" | "val" | "test">("auto")

  useEffect(() => {
    let isMounted = true
    const timer = setTimeout(() => {
      void Promise.all([
        getCategories().catch(() => [] as Category[]),
        getSkills().catch(() => ({ items: [] as Skill[], count: 0 })),
      ]).then(([cats, skillsRes]) => {
        if (!isMounted) return
        setCategories(cats)
        const items = skillsRes.items || []
        setCatalogSkills(items)
        if (items.length > 0) {
          const sportSkill =
            items.find((s) => {
              const cat = cats.find((c) => c.id === s.category_id)
              const cSlug = cat ? cat.slug.toLowerCase() : ""
              return (
                cSlug === "deporte" ||
                cSlug.includes("deport") ||
                cSlug.includes("futbol") ||
                s.name.toLowerCase().includes("dominada") ||
                s.name.toLowerCase().includes("fútbol")
              )
            }) || items[0]

          setSelectedSkillId(sportSkill.id)
          setSelectedSkillName(sportSkill.name)
          setDiscipline("fútbol")
          setChallenge(sportSkill.name)
        }
      }).catch(() => {
        // Ignorar errores al desmontar o sesión reseteada en tests
      })
    }, 0)
    return () => {
      isMounted = false
      clearTimeout(timer)
    }
  }, [setDiscipline, setChallenge])

  const categorySkills = useMemo(() => {
    return catalogSkills.filter((sk) => {
      const cat = categories.find((c) => c.id === sk.category_id)
      const cSlug = cat ? cat.slug.toLowerCase() : ""
      if (cSlug) {
        if (activeCategorySlug === "musica") return cSlug === "musica" || cSlug.includes("music")
        if (activeCategorySlug === "deporte") return cSlug === "deporte" || cSlug.includes("deport") || cSlug.includes("futbol")
        if (activeCategorySlug === "programacion") return cSlug === "programacion" || cSlug.includes("prog")
      }
      const name = sk.name.toLowerCase()
      if (activeCategorySlug === "musica") return name.includes("guitarra") || name.includes("piano") || name.includes("audio")
      if (activeCategorySlug === "deporte") return name.includes("dominada") || name.includes("fútbol") || name.includes("balón")
      if (activeCategorySlug === "programacion") return name.includes("python") || name.includes("react") || name.includes("código")
      return true
    })
  }, [catalogSkills, categories, activeCategorySlug])

  const handleSelectCategory = (slug: string) => {
    setActiveCategorySlug(slug)
    const skillsInCat = catalogSkills.filter((sk) => {
      const cat = categories.find((c) => c.id === sk.category_id)
      const cSlug = cat ? cat.slug.toLowerCase() : ""
      if (cSlug) {
        if (slug === "musica") return cSlug === "musica" || cSlug.includes("music")
        if (slug === "deporte") return cSlug === "deporte" || cSlug.includes("deport") || cSlug.includes("futbol")
        if (slug === "programacion") return cSlug === "programacion" || cSlug.includes("prog")
      }
      const name = sk.name.toLowerCase()
      if (slug === "musica") return name.includes("guitarra") || name.includes("piano") || name.includes("audio")
      if (slug === "deporte") return name.includes("dominada") || name.includes("fútbol") || name.includes("balón")
      if (slug === "programacion") return name.includes("python") || name.includes("react") || name.includes("código")
      return true
    })

    if (skillsInCat.length > 0) {
      const first = skillsInCat[0]
      setSelectedSkillId(first.id)
      setSelectedSkillName(first.name)
      const isFb =
        first.name.toLowerCase().includes("fútbol") ||
        first.name.toLowerCase().includes("dominada") ||
        first.name.toLowerCase().includes("balón")
      setDiscipline(isFb ? "fútbol" : slug)
      setChallenge(first.name)
    } else {
      setSelectedSkillId("")
      setSelectedSkillName("")
      setChallenge("")
    }
  }

  const handleSelectSkill = (skillId: string) => {
    setSelectedSkillId(skillId)
    const found = catalogSkills.find((s) => s.id === skillId)
    if (found) {
      setSelectedSkillName(found.name)
      const isFb =
        found.name.toLowerCase().includes("fútbol") ||
        found.name.toLowerCase().includes("dominada") ||
        found.name.toLowerCase().includes("balón")
      setDiscipline(isFb ? "fútbol" : activeCategorySlug)
      setChallenge(found.name)
    } else {
      setSelectedSkillName("")
      setChallenge("")
    }
  }

  const selectedSkill = catalogSkills.find((s) => s.id === selectedSkillId)

  useEffect(() => {
    fetchSamples()
  }, [fetchSamples])

  // Sincronizar video preview con mediaStream
  useEffect(() => {
    if (videoPreviewRef.current && mediaStream) {
      videoPreviewRef.current.srcObject = mediaStream
    }
  }, [mediaStream])

  // Limpieza al desmontar
  useEffect(() => {
    return () => {
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current)
      if (mediaStream) {
        mediaStream.getTracks().forEach((track) => track.stop())
      }
    }
  }, [mediaStream])

  const formatTimer = (totalSeconds: number) => {
    const mins = Math.floor(totalSeconds / 60)
    const secs = totalSeconds % 60
    return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`
  }

  const startMediaRecording = async (mode: "video" | "audio") => {
    resetRecording()
    try {
      if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
        throw new Error("El navegador o dispositivo no soporta captura multimedia nativa.")
      }

      const constraints: MediaStreamConstraints =
        mode === "video"
          ? { video: { width: 1280, height: 720 }, audio: true }
          : { audio: true }

      const stream = await navigator.mediaDevices.getUserMedia(constraints)
      setMediaStream(stream)

      const mimeType =
        mode === "video"
          ? MediaRecorder.isTypeSupported("video/mp4")
            ? "video/mp4"
            : "video/webm"
          : MediaRecorder.isTypeSupported("audio/wav")
          ? "audio/wav"
          : "audio/webm"

      const recorder = new MediaRecorder(stream, { mimeType })
      mediaRecorderRef.current = recorder
      chunksRef.current = []

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          chunksRef.current.push(event.data)
        }
      }

      recorder.onstop = async () => {
        const ext = mode === "video" ? "mp4" : "wav"
        const finalBlob = new Blob(chunksRef.current, { type: mimeType })
        await setRecordedBlob(finalBlob, `sample-${discipline}-${Date.now()}.${ext}`)
        stream.getTracks().forEach((track) => track.stop())
        setMediaStream(null)
      }

      recorder.start(500)
      setIsRecording(true)
      setRecordingDurationSeconds(0)

      timerIntervalRef.current = window.setInterval(() => {
        setRecordingDurationSeconds(useDatasetCaptureStore.getState().recordingDurationSeconds + 1)
      }, 1000)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "No se pudo acceder a los dispositivos de captura"
      useDatasetCaptureStore.setState({ error: msg })
    }
  }

  const stopMediaRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop()
    }
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current)
      timerIntervalRef.current = null
    }
    setIsRecording(false)
  }

  const handleManualFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = event.target.files
    if (!fileList || fileList.length === 0) return

    const newItems: BatchFileItem[] = []
    for (let i = 0; i < fileList.length; i++) {
      const f = fileList[i]
      const ext = f.name.split(".").pop()?.toLowerCase() || ""
      if (["mp4", "wav", "py"].includes(ext)) {
        newItems.push({
          id: `${f.name}-${f.size}-${Date.now()}-${i}`,
          file: f,
          name: f.name,
          size: f.size,
          format: ext,
          status: "idle",
        })
      }
    }

    if (newItems.length === 0) {
      useDatasetCaptureStore.setState({
        error: "Formato no permitido. Solo se aceptan archivos .mp4, .wav o .py.",
      })
      return
    }

    setBatchFiles((prev) => [...prev, ...newItems])

    // Mantener compatibilidad con archivo individual
    const first = newItems[0]
    if (first.format === "py") {
      const text = await first.file.text()
      setCodeContent(text)
      setRecordingMode("code")
    }
    await setRecordedBlob(first.file, first.name)
  }

  const handleRemoveBatchFile = (id: string) => {
    setBatchFiles((prev) => prev.filter((item) => item.id !== id))
  }

  const handleClearBatch = () => {
    setBatchFiles([])
    setBatchProgress(null)
    resetRecording()
  }

  const handleUploadSubmit = async () => {
    if (batchFiles.length > 0) {
      if (!signedConsent) {
        useDatasetCaptureStore.setState({
          error: "Debe otorgar el consentimiento explícito antes de subir la muestra.",
        })
        return
      }
      if ((discipline === "futbol" || activeCategorySlug === "deporte") && !levelLabel) {
        useDatasetCaptureStore.setState({
          error: "Seleccioná el nivel real del participante antes de subir las muestras.",
        })
        return
      }

      useDatasetCaptureStore.setState({ isUploading: true, error: null })
      let uploadedCount = 0

      const autoParticipantNumbers = samples
        .filter((s) => s.discipline.toLowerCase() === "futbol" && s.participant_id)
        .map((s) => {
          const match = /^anon-p(\d+)/.exec(s.participant_id || "")
          return match ? Number.parseInt(match[1], 10) : 0
        })
      const nextAutoParticipantNumber =
        (autoParticipantNumbers.length > 0 ? Math.max(...autoParticipantNumbers) : 0) + 1

      for (let i = 0; i < batchFiles.length; i++) {
        const item = batchFiles[i]
        setBatchProgress({
          current: i + 1,
          total: batchFiles.length,
          filename: item.name,
        })

        setBatchFiles((prev) =>
          prev.map((f) => (f.id === item.id ? { ...f, status: "hashing" } : f))
        )

        try {
          const hash = await calculateFileSha256(item.file)

          setBatchFiles((prev) =>
            prev.map((f) => (f.id === item.id ? { ...f, status: "uploading", sha256: hash } : f))
          )

          let itemSplit = split || "train"
          if (batchSplitMode === "auto") {
            const ratio = (i + 1) / batchFiles.length
            if (ratio <= 0.7) itemSplit = "train"
            else if (ratio <= 0.85) itemSplit = "val"
            else itemSplit = "test"
          } else {
            itemSplit = batchSplitMode
          }

          const itemParticipant = participantId.trim()
            ? (batchFiles.length > 1 ? `${participantId}-${i + 1}` : participantId)
            : `anon-p${String(nextAutoParticipantNumber + i).padStart(2, "0")}`

          const targetDiscipline =
            discipline === "futbol" || activeCategorySlug === "deporte"
              ? "futbol"
              : activeCategorySlug || discipline
          const targetChallenge = selectedSkillName || challenge || item.name
          const targetHardware = hardwareInfo.trim() || "Auto (Dispositivo Local)"
          const targetSurface = surface.trim() || "césped"

          await uploadDatasetSample({
            file: item.file,
            fileName: item.name,
            discipline: targetDiscipline,
            challenge: targetChallenge,
            hardware_info: targetHardware,
            signed_consent: signedConsent,
            file_hash_sha256: hash,
            participant_id: itemParticipant,
            level_label: levelLabel,
            manual_touch_count: manualTouchCount !== null ? manualTouchCount : undefined,
            noise_level: noiseLevel || "bajo",
            surface: targetSurface,
            split: itemSplit,
          })

          uploadedCount++
          setBatchFiles((prev) =>
            prev.map((f) => (f.id === item.id ? { ...f, status: "done" } : f))
          )
        } catch (err: unknown) {
          const msg = err instanceof Error ? err.message : "Error al subir muestra"
          setBatchFiles((prev) =>
            prev.map((f) => (f.id === item.id ? { ...f, status: "error", errorMessage: msg } : f))
          )
        }
      }

      useDatasetCaptureStore.setState({
        isUploading: false,
        lastUploadMessage: `¡Lote procesado exitosamente! Se subieron ${uploadedCount} de ${batchFiles.length} muestras reales al bucket Garage S3.`,
      })

      setBatchFiles((prev) => prev.filter((f) => f.status !== "done"))
      setBatchProgress(null)
      await fetchSamples(discipline === "all" ? undefined : discipline)
      return
    }

    // Subida unitaria estándar (grabación cámara/micrófono o código directo)
    const success = await uploadCurrentCapture()
    if (success) {
      chunksRef.current = []
    }
  }

  const filteredSamples =
    filterDiscipline === "all"
      ? samples
      : samples.filter((s) => s.discipline.toLowerCase() === filterDiscipline.toLowerCase())

  return (
    <div className="space-y-6 p-4 sm:p-6 max-w-7xl mx-auto">
      {/* Encabezado Principal */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border/60 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Badge variant="outline" className="border-emerald-500/40 text-emerald-500 bg-emerald-500/10">
              <ShieldCheck className="w-3.5 h-3.5 mr-1" /> Panel Exclusivo ADMIN
            </Badge>
            <Badge variant="secondary" className="font-mono text-xs">
              RF-IA-18 / HU-17
            </Badge>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground">
            Ingesta y Captura de Muestras Multimedia
          </h1>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={() => fetchSamples(filterDiscipline === "all" ? undefined : filterDiscipline)}
          disabled={isLoading}
          className="self-start md:self-auto"
        >
          <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? "animate-spin" : ""}`} />
          Refrescar Datasets
        </Button>
      </div>

      {/* Banner de Éxito con mensaje exacto del Backend */}
      {lastUploadMessage && (
        <Alert className="border-emerald-500/50 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 flex items-start justify-between">
          <div className="flex items-start gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-600 mt-0.5" />
            <div>
              <AlertTitle className="font-semibold">Servidor SkillMatch</AlertTitle>
              <AlertDescription className="text-sm">{lastUploadMessage}</AlertDescription>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={clearLastUploadMessage}
            className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground"
          >
            Cerrar
          </Button>
        </Alert>
      )}

      {/* Banner de Error */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Atención</AlertTitle>
          <AlertDescription className="text-sm">{error}</AlertDescription>
        </Alert>
      )}

      {/* Selector de 3 Categorías Canónicas y Selección de Habilidad */}
      <Card className="border-border/60 bg-card/60 backdrop-blur-sm shadow-sm">
        <CardHeader className="pb-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <CardTitle className="text-base font-semibold text-foreground">
                1. Selección de Categoría y Habilidad
              </CardTitle>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Pills de las 3 Categorías */}
          <div className="flex flex-wrap items-center gap-2.5">
            {CANONICAL_CATEGORIES.map((cat) => {
              const isSelected = activeCategorySlug === cat.slug
              return (
                <Button
                  key={cat.slug}
                  type="button"
                  variant={isSelected ? "default" : "outline"}
                  size="sm"
                  onClick={() => handleSelectCategory(cat.slug)}
                  className={
                    isSelected
                      ? "bg-emerald-600 hover:bg-emerald-700 text-white font-semibold shadow-xs"
                      : "border-border/60 bg-muted/20 text-muted-foreground hover:text-foreground hover:bg-muted/40"
                  }
                >
                  <span className="mr-1.5 text-base">{cat.icon}</span>
                  <span>{cat.name}</span>
                </Button>
              )
            })}
          </div>

          {/* Selector de Habilidad filtrado y Resumen */}
          <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-center pt-2 border-t border-border/40">
            <div className="md:col-span-5 space-y-1">
              <Label htmlFor="skill-selector" className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Habilidad del Catálogo *
              </Label>
              <Select
                value={selectedSkillId}
                onValueChange={handleSelectSkill}
              >
                <SelectTrigger id="skill-selector" className="w-full bg-background text-xs sm:text-sm">
                  <SelectValue placeholder="Seleccioná una habilidad del catálogo..." />
                </SelectTrigger>
                <SelectContent>
                  {categorySkills.length === 0 ? (
                    <SelectItem value="__none__" disabled>
                      Sin habilidades en esta categoría
                    </SelectItem>
                  ) : (
                    categorySkills.map((sk) => (
                      <SelectItem key={sk.id} value={sk.id}>
                        {sk.name}
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
            </div>

            {/* Tarjeta de Resumen de Habilidad Activa */}
            <div className="md:col-span-7">
              {selectedSkill ? (
                <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-lg border border-emerald-500/30 bg-emerald-500/5">
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                      <span className="font-bold text-sm text-foreground">{selectedSkill.name}</span>
                      <Badge variant="outline" className="text-[10px] border-emerald-500/40 text-emerald-600 capitalize">
                        {activeCategorySlug}
                      </Badge>
                    </div>
                    {selectedSkill.description && (
                      <p className="text-xs text-muted-foreground line-clamp-1">
                        {selectedSkill.description}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-xs">
                    <Badge variant="secondary" className="text-[11px]">
                      Umbral: {selectedSkill.min_approval_threshold}%
                    </Badge>
                    <Badge className={selectedSkill.is_ready_to_publish ? "bg-emerald-600 text-white text-[11px]" : "bg-muted text-muted-foreground text-[11px]"}>
                      {selectedSkill.is_ready_to_publish ? "Producción" : "Borrador"}
                    </Badge>
                  </div>
                </div>
              ) : (
                <div className="p-3 rounded-lg border border-amber-500/30 bg-amber-500/5 flex items-center gap-2 text-xs text-amber-700 dark:text-amber-400">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>Seleccioná una habilidad.</span>
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Selector de Módulo: Ingesta de Datasets vs Estudio de Entrenamiento vs Validador en Vivo */}
      <Tabs defaultValue="dataset-ingest" className="w-full space-y-6">
        <TabsList className="grid w-full max-w-3xl grid-cols-3">
          <TabsTrigger value="dataset-ingest" className="text-xs sm:text-sm">
            1. Ingesta de Datasets
          </TabsTrigger>
          <TabsTrigger
            value="football-training"
            className="text-xs sm:text-sm"
            data-testid="tab-football-training"
          >
            2. Estudio de Entrenamiento (IA)
          </TabsTrigger>
          <TabsTrigger
            value="football-live-validation"
            className="text-xs sm:text-sm"
            data-testid="tab-football-live-validation"
          >
            3. Validador en Vivo
          </TabsTrigger>
        </TabsList>

        <TabsContent value="football-training" className="space-y-6">
          <FootballTrainingStudio
            skillId={selectedSkillId}
            skillName={selectedSkillName}
          />
        </TabsContent>

        <TabsContent value="football-live-validation" className="space-y-6">
          <JugglingVideoAnalyzer />
          <FootballValidationWizard skillId={selectedSkillId} />
        </TabsContent>

        <TabsContent value="dataset-ingest" className="space-y-6">
          {/* Grid Central Responsive */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Columna Izquierda: Panel de Grabación & Ingesta */}
        <div className="lg:col-span-7 space-y-6">
          <Card className="border-border/60 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg font-semibold flex items-center justify-between">
                <span>1. Captura de Prueba Piloto</span>
                {isRecording && (
                  <Badge variant="destructive" className="animate-pulse flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-white animate-ping" />
                    REC {formatTimer(recordingDurationSeconds)}
                  </Badge>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <Tabs
                value={recordingMode}
                onValueChange={(val) => {
                  resetRecording()
                  setRecordingMode(val as "video" | "audio" | "code")
                }}
              >
                <TabsList className="grid grid-cols-3 w-full">
                  <TabsTrigger value="video" className="flex items-center gap-1.5 text-xs sm:text-sm">
                    <Video className="w-4 h-4 text-emerald-500" />
                    Video (Fútbol)
                  </TabsTrigger>
                  <TabsTrigger value="audio" className="flex items-center gap-1.5 text-xs sm:text-sm">
                    <Mic className="w-4 h-4 text-sky-500" />
                    Audio (Música)
                  </TabsTrigger>
                  <TabsTrigger value="code" className="flex items-center gap-1.5 text-xs sm:text-sm">
                    <Code className="w-4 h-4 text-violet-500" />
                    Código (AST)
                  </TabsTrigger>
                </TabsList>

                {/* Tab Video */}
                <TabsContent value="video" className="space-y-4 pt-3">
                  <div className="relative aspect-video rounded-lg overflow-hidden bg-neutral-950 flex items-center justify-center border border-border">
                    {mediaStream ? (
                      <video
                        ref={videoPreviewRef}
                        autoPlay
                        muted
                        playsInline
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="text-center p-6 text-muted-foreground space-y-2">
                        <Video className="w-12 h-12 mx-auto stroke-1 opacity-50 text-emerald-400" />
                        <p className="text-sm">Cámara inactiva.</p>
                      </div>
                    )}

                    {isRecording && (
                      <div className="absolute top-3 left-3 bg-red-600/90 text-white font-mono text-xs px-2.5 py-1 rounded-md shadow">
                        REC {formatTimer(recordingDurationSeconds)}
                      </div>
                    )}
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    {!isRecording ? (
                      <Button
                        type="button"
                        onClick={() => startMediaRecording("video")}
                        className="bg-emerald-600 hover:bg-emerald-700 text-white"
                      >
                        <Play className="w-4 h-4 mr-1.5 fill-current" />
                        Iniciar Grabación de Video
                      </Button>
                    ) : (
                      <Button type="button" variant="destructive" onClick={stopMediaRecording}>
                        <Square className="w-4 h-4 mr-1.5 fill-current" />
                        Detener y Procesar Muestra
                      </Button>
                    )}
                  </div>
                </TabsContent>

                {/* Tab Audio */}
                <TabsContent value="audio" className="space-y-4 pt-3">
                  <div className="p-8 rounded-lg bg-neutral-950 text-center border border-border space-y-3">
                    <Mic className={`w-14 h-14 mx-auto stroke-1 ${isRecording ? "text-red-500 animate-bounce" : "text-sky-400 opacity-60"}`} />
                    <p className="text-sm text-muted-foreground">
                      {isRecording
                        ? `Grabando espectro de audio... ${formatTimer(recordingDurationSeconds)}`
                        : "Micrófono listo."}
                    </p>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    {!isRecording ? (
                      <Button
                        type="button"
                        onClick={() => startMediaRecording("audio")}
                        className="bg-sky-600 hover:bg-sky-700 text-white"
                      >
                        <Mic className="w-4 h-4 mr-1.5" />
                        Iniciar Grabación de Audio
                      </Button>
                    ) : (
                      <Button type="button" variant="destructive" onClick={stopMediaRecording}>
                        <Square className="w-4 h-4 mr-1.5 fill-current" />
                        Detener y Guardar Audio (.wav)
                      </Button>
                    )}
                  </div>
                </TabsContent>

                {/* Tab Código */}
                <TabsContent value="code" className="space-y-4 pt-3">
                  <div className="space-y-2">
                    <Label htmlFor="code-editor" className="text-xs font-semibold text-muted-foreground flex items-center gap-1.5">
                      <FileCode className="w-3.5 h-3.5 text-violet-500" />
                      Editor de Código Python (.py) para Dataset AST
                    </Label>
                    <Textarea
                      id="code-editor"
                      rows={8}
                      className="font-mono text-xs bg-neutral-950 text-emerald-400 border-border"
                      value={codeContent}
                      onChange={(e) => {
                        setCodeContent(e.target.value)
                        setRecordedBlob(new Blob([e.target.value], { type: "text/x-python" }), "script.py")
                      }}
                      placeholder="def solution(): ..."
                    />
                  </div>
                </TabsContent>
              </Tabs>

              {/* Carga Múltiple de Archivos Reales */}
              <div className="pt-3 border-t border-border/60 space-y-3">
                <div className="flex items-center justify-between">
                  <Label htmlFor="file-upload" className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                    <UploadCloud className="w-4 h-4 text-emerald-500" />
                    Carga Múltiple de Archivos Reales (.mp4, .wav, .py):
                  </Label>
                  {batchFiles.length > 0 && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={handleClearBatch}
                      className="h-6 text-xs text-muted-foreground hover:text-destructive cursor-pointer"
                    >
                      Limpiar lista ({batchFiles.length})
                    </Button>
                  )}
                </div>
                <Input
                  id="file-upload"
                  type="file"
                  multiple
                  accept=".mp4,.wav,.py,video/mp4,audio/wav,text/x-python"
                  onChange={handleManualFileUpload}
                  className="cursor-pointer file:cursor-pointer text-xs"
                />
                {/* Cola de Archivos Seleccionados */}
                {batchFiles.length > 0 && (
                  <div className="space-y-2 border border-border/70 rounded-lg p-3 bg-card/40 max-h-56 overflow-y-auto">
                    <div className="text-xs font-semibold text-foreground flex items-center justify-between">
                      <span>Archivos en lote ({batchFiles.length}):</span>
                      <span className="text-muted-foreground font-mono text-[11px]">
                        {(batchFiles.reduce((acc, f) => acc + f.size, 0) / (1024 * 1024)).toFixed(1)} MB total
                      </span>
                    </div>
                    <div className="space-y-1.5">
                      {batchFiles.map((item, idx) => (
                        <div
                          key={item.id}
                          className="flex items-center justify-between p-2 rounded bg-background/60 border border-border/40 text-xs"
                        >
                          <div className="flex items-center gap-2 truncate max-w-[260px]">
                            <span className="font-mono text-muted-foreground text-[10px]">#{idx + 1}</span>
                            <Badge variant="secondary" className="text-[10px] uppercase font-mono">
                              .{item.format}
                            </Badge>
                            <span className="truncate font-medium text-foreground" title={item.name}>
                              {item.name}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            <span className="text-[10px] text-muted-foreground font-mono">
                              {(item.size / (1024 * 1024)).toFixed(1)} MB
                            </span>
                            {item.status === "done" && (
                              <Badge className="bg-emerald-600 text-white text-[10px] flex items-center gap-1">
                                <CheckCircle2 className="w-3 h-3" /> Subido
                              </Badge>
                            )}
                            {item.status === "uploading" && (
                              <Badge variant="outline" className="border-sky-500/40 text-sky-500 text-[10px] animate-pulse">
                                Subiendo...
                              </Badge>
                            )}
                            {item.status === "hashing" && (
                              <Badge variant="outline" className="border-amber-500/40 text-amber-500 text-[10px]">
                                SHA-256...
                              </Badge>
                            )}
                            {item.status === "error" && (
                              <Badge variant="destructive" className="text-[10px]">
                                Error
                              </Badge>
                            )}
                            {item.status === "idle" && (
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={() => handleRemoveBatchFile(item.id)}
                                className="h-5 w-5 p-0 text-muted-foreground hover:text-destructive cursor-pointer"
                              >
                                <Trash2 className="w-3 h-3" />
                              </Button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Vista previa de archivo capturado y Hash SHA-256 */}
              {recordedBlob && batchFiles.length <= 1 && (
                <div className="p-3.5 rounded-lg bg-secondary/50 border border-border/80 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <FileCheck className="w-4 h-4 text-emerald-500" />
                      <span className="text-xs font-medium text-foreground truncate max-w-[200px]">
                        {recordedFileName}
                      </span>
                      <Badge variant="outline" className="text-[10px] uppercase">
                        {(recordedBlob.size / 1024).toFixed(1)} KB
                      </Badge>
                    </div>
                    <Button variant="ghost" size="sm" onClick={resetRecording} className="h-7 text-xs text-muted-foreground hover:text-destructive">
                      Descartar
                    </Button>
                  </div>

                  <div className="flex items-center gap-1.5 text-[11px] font-mono text-muted-foreground bg-background/60 p-2 rounded border border-border/40 overflow-x-auto">
                    <Hash className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                    <span className="shrink-0 text-foreground font-semibold">SHA-256:</span>
                    <span className="truncate">{recordedFileHash || "Calculando hash..."}</span>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Formulario de Metadatos y Consentimiento */}
          <Card className="border-border/60 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg font-semibold flex items-center justify-between">
                <span>2. Metadatos & Consentimiento</span>
                <Badge variant="outline" className="border-emerald-500/40 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 text-[11px] flex items-center gap-1 font-normal">
                  <Sparkles className="w-3 h-3 text-emerald-500" /> Automático
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {(discipline === "futbol" || activeCategorySlug === "deporte") && !levelLabel && (
                <div className="flex items-center gap-2 p-2.5 rounded-lg border border-amber-500/40 bg-amber-500/10 text-xs text-amber-700 dark:text-amber-400">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>Falta elegir el nivel real del participante, abajo en “Opciones avanzadas”.</span>
                </div>
              )}

              {/* Acordeón Opcional para Investigadores / Configuración Manual */}
              <details
                className="group border border-border/50 rounded-lg p-3 bg-card/40 transition-all"
                open={discipline === "futbol" || activeCategorySlug === "deporte" ? true : undefined}
              >
                <summary className="text-xs font-medium text-muted-foreground hover:text-foreground cursor-pointer flex items-center justify-between select-none">
                  <span className="flex items-center gap-1.5">
                    <SlidersHorizontal className="w-3.5 h-3.5 text-muted-foreground" />
                    Opciones avanzadas y etiquetado manual (opcional)
                  </span>
                  <ChevronDown className="w-4 h-4 text-muted-foreground transition-transform group-open:rotate-180" />
                </summary>
                <div className="pt-3 space-y-4 mt-2 border-t border-border/40 text-xs">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <Label htmlFor="discipline-select" className="text-xs font-medium">Disciplina</Label>
                      <Select value={discipline} onValueChange={setDiscipline}>
                        <SelectTrigger id="discipline-select" className="w-full">
                          <SelectValue placeholder="Selecciona disciplina" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="musica">Música e Instrumentos</SelectItem>
                          <SelectItem value="futbol">Deportes y Fútbol</SelectItem>
                          <SelectItem value="programacion">Programación y Software</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-1.5">
                      <Label htmlFor="challenge-input" className="text-xs font-medium">Reto / Desafío</Label>
                      <Input
                        id="challenge-input"
                        value={challenge}
                        onChange={(e) => setChallenge(e.target.value)}
                        placeholder={selectedSkillName || "Ej. Dominadas de Balón"}
                      />
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="hardware-input" className="text-xs font-medium flex items-center gap-1.5">
                      <Cpu className="w-3.5 h-3.5 text-muted-foreground" />
                      Hardware / Periféricos Utilizados
                    </Label>
                    <Input
                      id="hardware-input"
                      value={hardwareInfo}
                      onChange={(e) => setHardwareInfo(e.target.value)}
                      placeholder="Ej. Logitech C920 Webcam + Micrófono Samson Go"
                    />
                  </div>

                  {(discipline === "futbol" || activeCategorySlug === "deporte") && (
                    <div className="p-3 rounded-lg border border-border/70 bg-secondary/10 space-y-3">
                      <p className="text-xs font-semibold text-foreground">
                        Etiquetado Manual de Fútbol (Opcional)
                      </p>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        <div className="space-y-1">
                          <Label htmlFor="participant-id-input" className="text-xs">
                            ID Participante
                          </Label>
                          <Input
                            id="participant-id-input"
                            value={participantId}
                            onChange={(e) => setParticipantId(e.target.value)}
                            placeholder="Auto (Ej. anon-p01)"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label htmlFor="manual-touch-input" className="text-xs">
                            Conteo Manual de Toques
                          </Label>
                          <Input
                            id="manual-touch-input"
                            type="number"
                            min={0}
                            value={manualTouchCount ?? ""}
                            onChange={(e) =>
                              setManualTouchCount(
                                e.target.value === "" ? null : Number(e.target.value)
                              )
                            }
                            placeholder="Opcional (Auto-detectado)"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label htmlFor="level-label-select" className="text-xs">
                            Nivel real del participante *
                          </Label>
                          <Select value={levelLabel} onValueChange={setLevelLabel}>
                            <SelectTrigger
                              id="level-label-select"
                              className={!levelLabel ? "border-amber-500/50" : undefined}
                            >
                              <SelectValue placeholder="Seleccioná un nivel..." />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="Principiante">Principiante</SelectItem>
                              <SelectItem value="Intermedio">Intermedio</SelectItem>
                              <SelectItem value="Avanzado">Avanzado</SelectItem>
                              <SelectItem value="Experto">Experto</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        <div className="space-y-1">
                          <Label htmlFor="noise-level-select" className="text-xs">
                            Ruido Ambiental
                          </Label>
                          <Select value={noiseLevel} onValueChange={setNoiseLevel}>
                            <SelectTrigger id="noise-level-select">
                              <SelectValue placeholder="Ruido" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="bajo">Bajo (Predeterminado)</SelectItem>
                              <SelectItem value="medio">Medio</SelectItem>
                              <SelectItem value="alto">Alto</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-1">
                          <Label htmlFor="surface-input" className="text-xs">
                            Superficie
                          </Label>
                          <Input
                            id="surface-input"
                            value={surface}
                            onChange={(e) => setSurface(e.target.value)}
                            placeholder="Césped (Predeterminado)"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label htmlFor="split-select" className="text-xs">
                            Partición (Split)
                          </Label>
                          <Select
                            value={batchFiles.length > 1 ? batchSplitMode : split}
                            onValueChange={(val: "auto" | "train" | "val" | "test") => {
                              setBatchSplitMode(val)
                              setSplit(val === "auto" ? "train" : val)
                            }}
                          >
                            <SelectTrigger id="split-select">
                              <SelectValue placeholder="Split" />
                            </SelectTrigger>
                            <SelectContent>
                              {batchFiles.length > 1 && (
                                <SelectItem value="auto">Auto (70% Train / 15% Val / 15% Test)</SelectItem>
                              )}
                              <SelectItem value="train">Train (Entrenamiento)</SelectItem>
                              <SelectItem value="val">Validation (Calibración)</SelectItem>
                              <SelectItem value="test">Test (Prueba Ciega)</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </details>

              {/* Consentimiento firmado obligatorio */}
              <div className="flex items-start gap-3 p-3.5 rounded-lg border border-emerald-500/30 bg-emerald-500/5">
                <Switch
                  id="consent-switch"
                  checked={signedConsent}
                  onCheckedChange={setSignedConsent}
                  className="mt-0.5"
                />
                <div className="space-y-1">
                  <Label htmlFor="consent-switch" className="text-xs font-semibold cursor-pointer text-foreground">
                    Consentimiento Informado Firmado (Requisito Legal Estricto)
                  </Label>
                  <p className="text-[11px] text-muted-foreground leading-relaxed">
                    Certifico que el sujeto participante firmó explícitamente el consentimiento para capturar audio, video o código.
                  </p>
                </div>
              </div>

              {/* Botón de Subida */}
              <Button
                type="button"
                className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-2.5 shadow-sm disabled:opacity-50"
                disabled={
                  isUploading ||
                  !signedConsent ||
                  (batchFiles.length === 0 && !recordedBlob && recordingMode !== "code")
                }
                onClick={handleUploadSubmit}
              >
                {isUploading ? (
                  <>
                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                    {batchProgress
                      ? `Subiendo muestra ${batchProgress.current} de ${batchProgress.total}: ${batchProgress.filename}...`
                      : "Validando Hash SHA-256 y Almacenando en Servidor..."}
                  </>
                ) : (
                  <>
                    <UploadCloud className="w-4 h-4 mr-2" />
                    {batchFiles.length > 1
                      ? `Subir Lote de ${batchFiles.length} Muestras Reales a Garage S3`
                      : "Subir Muestra al Dataset de IA (Multipart)"}
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Columna Derecha: Catálogo de Muestras Capturadas */}
        <div className="lg:col-span-5 space-y-6">
          <Card className="border-border/60 shadow-sm">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-lg font-semibold">Muestras Ingestadas</CardTitle>
                  <CardDescription>
                    Total recolectado: {totalCount} {totalCount === 1 ? "muestra" : "muestras"}
                  </CardDescription>
                </div>
                <Select value={filterDiscipline} onValueChange={setFilterDiscipline}>
                  <SelectTrigger className="w-[140px] text-xs">
                    <SelectValue placeholder="Disciplina" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Todas</SelectItem>
                    <SelectItem value="musica">Música</SelectItem>
                    <SelectItem value="futbol">Fútbol</SelectItem>
                    <SelectItem value="programacion">Código</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {filteredSamples.length === 0 ? (
                <div className="text-center py-12 px-4 text-muted-foreground space-y-2">
                  <UploadCloud className="w-10 h-10 mx-auto stroke-1 opacity-40 text-muted-foreground" />
                  <p className="text-sm">Sin muestras todavía.</p>
                </div>
              ) : (
                <div className="overflow-x-auto max-h-[640px] overflow-y-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="text-xs">Formato & Reto</TableHead>
                        <TableHead className="text-xs">Hash SHA-256</TableHead>
                        <TableHead className="text-xs text-right">Acción</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredSamples.map((sample) => (
                        <TableRow key={sample.id}>
                          <TableCell className="py-3">
                            <div className="space-y-0.5">
                              <div className="flex items-center gap-1.5">
                                <Badge variant="secondary" className="text-[10px] font-mono uppercase">
                                  .{sample.file_format}
                                </Badge>
                                <span className="text-xs font-semibold text-foreground truncate max-w-[130px]">
                                  {sample.challenge}
                                </span>
                              </div>
                              <p className="text-[11px] text-muted-foreground capitalize">
                                {sample.discipline} • {(sample.file_size_bytes / 1024).toFixed(0)} KB
                              </p>
                              <p className="text-[10px] text-muted-foreground truncate max-w-[160px]">
                                {sample.hardware_info}
                              </p>
                            </div>
                          </TableCell>
                          <TableCell className="py-3">
                            <div className="font-mono text-[10px] text-muted-foreground bg-muted/60 p-1.5 rounded max-w-[130px] truncate" title={sample.file_hash_sha256}>
                              {sample.file_hash_sha256.slice(0, 12)}...{sample.file_hash_sha256.slice(-8)}
                            </div>
                          </TableCell>
                          <TableCell className="py-3 text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground"
                              onClick={() => handlePreviewSample(sample.id)}
                              disabled={loadingPreviewId === sample.id}
                              aria-label="Ver muestra"
                              title="Ver muestra"
                            >
                              <Eye className="w-4 h-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive"
                              onClick={() => deleteSampleById(sample.id)}
                              title="Eliminar muestra defectuosa"
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
        </TabsContent>
      </Tabs>

      <Dialog open={previewSample !== null} onOpenChange={(open) => !open && setPreviewSample(null)}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Vista previa de la muestra</DialogTitle>
          </DialogHeader>
          {previewSample?.format === "mp4" ? (
            <video src={previewSample.url} controls autoPlay className="w-full rounded-lg" />
          ) : previewSample?.format === "wav" ? (
            <audio src={previewSample.url} controls autoPlay className="w-full" />
          ) : previewSample ? (
            <pre className="text-xs bg-neutral-950 text-emerald-400 p-4 rounded-lg overflow-auto max-h-[60vh]">
              <a href={previewSample.url} target="_blank" rel="noreferrer" className="underline">
                Abrir archivo
              </a>
            </pre>
          ) : null}
        </DialogContent>
      </Dialog>

      {previewError && (
        <Alert variant="destructive" className="fixed bottom-4 right-4 w-auto max-w-sm z-50">
          <AlertTitle>No se pudo previsualizar</AlertTitle>
          <AlertDescription className="text-sm">{previewError}</AlertDescription>
        </Alert>
      )}
    </div>
  )
}

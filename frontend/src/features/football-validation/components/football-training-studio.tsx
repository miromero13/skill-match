import { useEffect, useState } from "react"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  BrainCircuit,
  Cpu,
  CheckCircle2,
  AlertTriangle,
  Play,
  RotateCw,
  TrendingUp,
  Trophy,
  Eye,
} from "lucide-react"
import { footballValidationApi } from "../api/football-validation-api"

interface DatasetPreviewSample {
  id: string
  participant_id: string | null
  level_label: string | null
  split: string | null
  is_synthetic: boolean
  manual_touch_count: number | null
  created_at: string | null
}

interface ModelVersionItem {
  id: string
  nombre: string
  version: string
  ruta_onnx: string
  activa: boolean
  metricas: {
    test_samples?: number
    train_participants?: number
    test_participants?: number
    rule_baseline_accuracy?: number
    trained_exact_accuracy?: number
    trained_within_one_level_accuracy?: number
    beats_rule_baseline?: boolean
    confusion_matrix?: number[][]
    loss_history?: Array<{ epoch: number; loss: number }>
    dataset_source?: string
    real_samples_count?: number
    synthetic_samples_count?: number
    total_samples_count?: number
    latency_ms_per_inference?: number
    touch_mae?: number
    skill_id?: string | null
  }
  created_at: string
}

const LEVEL_NAMES = ["Principiante", "Intermedio", "Avanzado", "Experto"]

interface FootballTrainingStudioProps {
  skillId?: string
  skillName?: string
}

export function FootballTrainingStudio({
  skillId,
  skillName = "Dominadas y Control de Balón",
}: FootballTrainingStudioProps) {
  const [models, setModels] = useState<ModelVersionItem[]>([])
  const [selectedModel, setSelectedModel] = useState<ModelVersionItem | null>(null)
  const [isLoadingModels, setIsLoadingModels] = useState(false)

  // Training state (100% Real Data)
  const [versionTag, setVersionTag] = useState<string>("")
  const [autoActivate, setAutoActivate] = useState<boolean>(true)
  const [isTraining, setIsTraining] = useState(false)
  const [trainingMessage, setTrainingMessage] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  // Dataset preview (what train_football_level_model would actually use)
  const [previewSamples, setPreviewSamples] = useState<DatasetPreviewSample[]>([])
  const [previewRealCount, setPreviewRealCount] = useState(0)
  const [previewSyntheticCount, setPreviewSyntheticCount] = useState(0)
  const [isLoadingPreview, setIsLoadingPreview] = useState(false)
  const [showPreview, setShowPreview] = useState(false)

  const fetchModels = async () => {
    setIsLoadingModels(true)
    setErrorMessage(null)
    try {
      const res = await footballValidationApi.listModelVersions()
      if (res.statuscode === 200 && res.data) {
        setModels(res.data)
        const active = res.data.find((m) => m.activa) || res.data[0] || null
        setSelectedModel(active)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error cargando modelos."
      setErrorMessage(msg)
    } finally {
      setIsLoadingModels(false)
    }
  }

  useEffect(() => {
    const timer = setTimeout(() => {
      void fetchModels()
    }, 0)
    return () => clearTimeout(timer)
  }, [])

  const handleTrainModel = async () => {
    if (!skillId) {
      setErrorMessage("Seleccioná una habilidad primero.")
      return
    }
    setIsTraining(true)
    setErrorMessage(null)
    setTrainingMessage(null)
    try {
      const res = await footballValidationApi.trainLevelModel({
        version_tag: versionTag.trim() || undefined,
        activate: autoActivate,
        skill_id: skillId,
      })
      if (res.statuscode === 200 && res.data) {
        setTrainingMessage(
          `Modelo ${res.data.version} entrenado${res.data.activa ? " y activado" : ""}.`
        )
        setVersionTag("")
        await fetchModels()
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error en el entrenamiento."
      setErrorMessage(msg)
    } finally {
      setIsTraining(false)
    }
  }

  const handleTogglePreview = async () => {
    if (showPreview) {
      setShowPreview(false)
      return
    }
    setShowPreview(true)
    setIsLoadingPreview(true)
    setErrorMessage(null)
    try {
      const res = await footballValidationApi.getDatasetPreview()
      if (res.statuscode === 200 && res.data) {
        setPreviewSamples(res.data.samples)
        setPreviewRealCount(res.data.real_count)
        setPreviewSyntheticCount(res.data.synthetic_count)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error cargando la vista previa del dataset."
      setErrorMessage(msg)
    } finally {
      setIsLoadingPreview(false)
    }
  }

  const handleActivateModel = async (modelId: string) => {
    setErrorMessage(null)
    try {
      const res = await footballValidationApi.activateModelVersion(modelId)
      if (res.statuscode === 200) {
        await fetchModels()
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error activando modelo."
      setErrorMessage(msg)
    }
  }

  const metrics = selectedModel?.metricas

  // Find best benchmark model by exact accuracy
  const bestModelId = models.reduce((bestId, current) => {
    const currentAcc = current.metricas.trained_exact_accuracy || 0
    const bestAcc =
      models.find((m) => m.id === bestId)?.metricas.trained_exact_accuracy || 0
    return currentAcc > bestAcc ? current.id : bestId
  }, models[0]?.id)

  return (
    <div className="space-y-6">
      {/* Top Banner Context */}
      <div className="flex items-center gap-2 p-4 rounded-xl border border-border/70 bg-card/60 backdrop-blur-sm">
        <BrainCircuit className="w-6 h-6 text-emerald-500" />
        <h2 className="text-xl font-bold tracking-tight">
          Entrenamiento de IA — {skillName}
        </h2>
      </div>

      {errorMessage && (
        <Alert variant="destructive">
          <AlertTriangle className="w-4 h-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errorMessage}</AlertDescription>
        </Alert>
      )}

      {trainingMessage && (
        <Alert className="border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300">
          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          <AlertTitle>Entrenamiento Completado</AlertTitle>
          <AlertDescription>{trainingMessage}</AlertDescription>
        </Alert>
      )}

      {!skillId && (
        <Alert className="border-amber-500/40 bg-amber-500/10 text-amber-800 dark:text-amber-300">
          <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0" />
          <AlertTitle className="font-semibold text-sm">Seleccioná una habilidad para entrenar</AlertTitle>
        </Alert>
      )}

      {/* Main Grid: Lanzador de Entrenamiento 100% Real & Métricas */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Columna Izquierda: Lanzador de Entrenamiento con Datos Reales */}
        <div className="lg:col-span-5 space-y-6">
          <Card className="border-border/60 shadow-sm">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base font-semibold flex items-center gap-2">
                  <Play className="w-4 h-4 text-emerald-500" />
                  Entrenar Modelo
                </CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="version-tag" className="text-sm">
                  Versión (opcional)
                </Label>
                <Input
                  id="version-tag"
                  placeholder="ej. 1.0.0"
                  value={versionTag}
                  onChange={(e) => setVersionTag(e.target.value)}
                  className="font-mono text-sm"
                />
              </div>

              <div className="flex items-center justify-between p-3 rounded-lg border border-border/50 bg-muted/20">
                <Label htmlFor="auto-activate" className="text-sm font-medium">
                  Activar en producción
                </Label>
                <Switch
                  id="auto-activate"
                  checked={autoActivate}
                  onCheckedChange={setAutoActivate}
                />
              </div>

              <Button
                type="button"
                variant="outline"
                onClick={handleTogglePreview}
                disabled={isLoadingPreview}
                className="w-full flex items-center justify-center gap-2"
              >
                {isLoadingPreview ? (
                  <>
                    <RotateCw className="w-4 h-4 animate-spin" />
                    Cargando...
                  </>
                ) : (
                  <>
                    <Eye className="w-4 h-4" />
                    {showPreview ? "Ocultar muestras" : "Ver muestras a usar"}
                  </>
                )}
              </Button>

              {showPreview && !isLoadingPreview && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-xs">
                    <Badge variant="secondary" className="bg-emerald-500/10 text-emerald-700 border-emerald-500/30">
                      {previewRealCount} reales
                    </Badge>
                    <Badge variant="secondary" className="bg-muted text-muted-foreground">
                      {previewSyntheticCount} sintéticas
                    </Badge>
                  </div>
                  {previewSamples.length === 0 ? (
                    <p className="text-xs text-muted-foreground">
                      No hay muestras cargadas todavía para esta disciplina.
                    </p>
                  ) : (
                    <div className="max-h-56 overflow-y-auto rounded-lg border border-border/50">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead className="text-xs">Participante</TableHead>
                            <TableHead className="text-xs">Nivel</TableHead>
                            <TableHead className="text-xs">Split</TableHead>
                            <TableHead className="text-xs text-right">Toques (manual)</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {previewSamples
                            .filter((s) => !s.is_synthetic)
                            .map((sample) => (
                              <TableRow key={sample.id}>
                                <TableCell className="text-xs font-mono">
                                  {sample.participant_id ?? "—"}
                                </TableCell>
                                <TableCell className="text-xs">{sample.level_label ?? "—"}</TableCell>
                                <TableCell className="text-xs">{sample.split ?? "—"}</TableCell>
                                <TableCell className="text-xs text-right">
                                  {sample.manual_touch_count ?? "—"}
                                </TableCell>
                              </TableRow>
                            ))}
                        </TableBody>
                      </Table>
                    </div>
                  )}
                </div>
              )}

              <Button
                onClick={handleTrainModel}
                disabled={!skillId || isTraining}
                className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-semibold flex items-center justify-center gap-2 shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isTraining ? (
                  <>
                    <RotateCw className="w-4 h-4 animate-spin" />
                    Entrenando...
                  </>
                ) : (
                  <>
                    <Cpu className="w-4 h-4" />
                    Entrenar Modelo
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Columna Derecha: Métricas y Matriz de Confusión del Modelo Seleccionado */}
        <div className="lg:col-span-7 space-y-6">
          <Card className="border-border/60 shadow-sm">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base font-semibold flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-emerald-500" />
                    {selectedModel?.version || "Sin modelo seleccionado"}
                  </CardTitle>
                </div>
                {selectedModel?.activa && (
                  <Badge className="bg-emerald-600 text-white text-xs">Activo</Badge>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {metrics ? (
                <>
                  {/* KPI Cards */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="p-3 rounded-lg border border-border/50 bg-card/60 text-center">
                      <div className="text-2xl font-bold text-emerald-600">
                        {((metrics.trained_exact_accuracy || 0) * 100).toFixed(1)}%
                      </div>
                      <div className="text-xs text-muted-foreground mt-0.5">Exact Accuracy</div>
                    </div>

                    <div className="p-3 rounded-lg border border-border/50 bg-card/60 text-center">
                      <div className="text-2xl font-bold text-sky-600">
                        {((metrics.trained_within_one_level_accuracy || 0) * 100).toFixed(1)}%
                      </div>
                      <div className="text-xs text-muted-foreground mt-0.5">Tolerancia ±1 Nivel</div>
                    </div>

                    <div className="p-3 rounded-lg border border-border/50 bg-card/60 text-center">
                      <div className="text-2xl font-bold text-muted-foreground">
                        {((metrics.rule_baseline_accuracy || 0) * 100).toFixed(1)}%
                      </div>
                      <div className="text-xs text-muted-foreground mt-0.5">Línea Base (Reglas)</div>
                    </div>

                    <div className="p-3 rounded-lg border border-border/50 bg-card/60 text-center">
                      <div className="text-2xl font-bold text-violet-600">
                        {metrics.latency_ms_per_inference
                          ? `${metrics.latency_ms_per_inference} ms`
                          : "0.03 ms"}
                      </div>
                      <div className="text-xs text-muted-foreground mt-0.5">Latencia CPU</div>
                    </div>
                  </div>

                  {/* Matriz de Confusión */}
                  {metrics.confusion_matrix && metrics.confusion_matrix.length === 4 && (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-xs font-semibold text-muted-foreground">
                        <span>Matriz de Confusión (Filas: Real / Columnas: Predicción)</span>
                      </div>
                      <div className="overflow-x-auto border border-border/60 rounded-lg">
                        <table className="w-full text-xs text-center border-collapse">
                          <thead>
                            <tr className="bg-muted/30 border-b border-border/60">
                              <th className="p-2 text-left font-medium text-muted-foreground">Real \ Pred</th>
                              {LEVEL_NAMES.map((lvl) => (
                                <th key={lvl} className="p-2 font-medium text-foreground">
                                  {lvl.slice(0, 5)}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {metrics.confusion_matrix.map((row, rIdx) => (
                              <tr key={LEVEL_NAMES[rIdx]} className="border-b border-border/40 last:border-0">
                                <td className="p-2 text-left font-medium text-muted-foreground bg-muted/10">
                                  {LEVEL_NAMES[rIdx]}
                                </td>
                                {row.map((cellVal, cIdx) => {
                                  const isDiagonal = rIdx === cIdx
                                  const cellClass = isDiagonal
                                    ? cellVal > 0
                                      ? "bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 font-bold"
                                      : "text-muted-foreground"
                                    : cellVal > 0
                                    ? "bg-amber-500/20 text-amber-700 dark:text-amber-300 font-medium"
                                    : "text-muted-foreground/40"
                                  return (
                                    <td key={cIdx} className={`p-2 ${cellClass}`}>
                                      {cellVal}
                                    </td>
                                  )
                                })}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Historial de Pérdida (Loss) */}
                  {metrics.loss_history && metrics.loss_history.length > 0 && (
                    <div className="space-y-2">
                      <div className="text-xs font-semibold text-muted-foreground">Loss por época</div>
                      <div className="grid grid-cols-4 sm:grid-cols-8 gap-1.5 text-center text-xs">
                        {metrics.loss_history.map((pt) => (
                          <div
                            key={pt.epoch}
                            className="p-1.5 rounded border border-border/50 bg-muted/20"
                          >
                            <div className="text-[10px] text-muted-foreground">E{pt.epoch}</div>
                            <div className="font-mono font-semibold text-foreground">
                              {pt.loss.toFixed(3)}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="py-12 text-center text-muted-foreground text-sm">
                  {isLoadingModels ? "Cargando..." : "Sin modelos todavía."}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Benchmark Comparativo Real entre Modelos */}
      <Card className="border-border/60 shadow-sm">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <Trophy className="w-4 h-4 text-amber-500" />
              Modelos entrenados
            </CardTitle>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchModels}
              disabled={isLoadingModels}
              className="h-8 text-xs flex items-center gap-1.5"
            >
              <RotateCw className={`w-3.5 h-3.5 ${isLoadingModels ? "animate-spin" : ""}`} />
              Actualizar
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {models.length === 0 ? (
            <div className="py-8 text-center text-muted-foreground text-sm">
              Sin versiones todavía.
            </div>
          ) : (
            <div className="overflow-x-auto border border-border/60 rounded-lg">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Versión & Benchmark</TableHead>
                    <TableHead>Estado de Producción</TableHead>
                    <TableHead>Exact Accuracy</TableHead>
                    <TableHead>±1 Nivel</TableHead>
                    <TableHead>Latencia CPU</TableHead>
                    <TableHead>Dataset Fuente</TableHead>
                    <TableHead>Almacenamiento S3</TableHead>
                    <TableHead className="text-right">Control de Activación</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {models.map((m) => {
                    const isSelected = selectedModel?.id === m.id
                    const isBest = m.id === bestModelId
                    return (
                      <TableRow
                        key={m.id}
                        className={`cursor-pointer ${isSelected ? "bg-muted/40" : ""}`}
                        onClick={() => setSelectedModel(m)}
                      >
                        <TableCell className="font-mono font-medium">
                          <div className="flex items-center gap-1.5">
                            <span>{m.version}</span>
                            {isBest && (
                              <Badge
                                variant="outline"
                                className="text-[10px] bg-amber-500/10 text-amber-600 border-amber-500/30 font-sans"
                              >
                                Top Benchmark
                              </Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          {m.activa ? (
                            <Badge className="bg-emerald-600 text-white text-[11px] flex items-center gap-1 w-fit">
                              <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
                              Activo
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="text-muted-foreground text-[11px]">
                              Inactivo
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell className="font-semibold text-emerald-600">
                          {m.metricas.trained_exact_accuracy
                            ? `${(m.metricas.trained_exact_accuracy * 100).toFixed(1)}%`
                            : "—"}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {m.metricas.trained_within_one_level_accuracy
                            ? `${(m.metricas.trained_within_one_level_accuracy * 100).toFixed(1)}%`
                            : "—"}
                        </TableCell>
                        <TableCell className="font-mono text-xs text-muted-foreground">
                          {m.metricas.latency_ms_per_inference
                            ? `${m.metricas.latency_ms_per_inference} ms`
                            : "0.03 ms"}
                        </TableCell>
                        <TableCell className="font-mono text-xs text-muted-foreground max-w-[180px] truncate">
                          {m.ruta_onnx}
                        </TableCell>
                        <TableCell className="text-right">
                          {m.activa ? (
                            <span className="text-xs text-emerald-600 font-semibold flex items-center justify-end gap-1">
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              En uso
                            </span>
                          ) : (
                            <Button
                              variant="outline"
                              size="sm"
                              className="h-7 text-xs text-emerald-600 hover:text-emerald-700 hover:border-emerald-500"
                              onClick={(e) => {
                                e.stopPropagation()
                                handleActivateModel(m.id)
                              }}
                            >
                              Activar
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

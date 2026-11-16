import { useEffect, useState } from "react"
import {
  Card,
  CardContent,
  CardDescription,
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
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  Play,
  RotateCw,
  Database,
  Layers,
  TrendingUp,
  Cloud,
} from "lucide-react"
import { footballValidationApi } from "../api/football-validation-api"

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
  }
  created_at: string
}

const LEVEL_NAMES = ["Principiante", "Intermedio", "Avanzado", "Experto"]

export function FootballTrainingStudio() {
  const [models, setModels] = useState<ModelVersionItem[]>([])
  const [selectedModel, setSelectedModel] = useState<ModelVersionItem | null>(null)
  const [isLoadingModels, setIsLoadingModels] = useState(false)

  // Synthetic Generator state
  const [synthCount, setSynthCount] = useState<number>(12)
  const [isGenerating, setIsGenerating] = useState(false)
  const [generationSummary, setGenerationSummary] = useState<{
    count: number
    splits: Record<string, number>
    levels: Record<string, number>
  } | null>(null)

  // Training state
  const [versionTag, setVersionTag] = useState<string>("")
  const [autoActivate, setAutoActivate] = useState<boolean>(true)
  const [isTraining, setIsTraining] = useState(false)
  const [trainingMessage, setTrainingMessage] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

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

  const handleGenerateSynthetic = async () => {
    setIsGenerating(true)
    setErrorMessage(null)
    setGenerationSummary(null)
    try {
      const res = await footballValidationApi.generateSyntheticDataset({
        count: synthCount,
        train_ratio: 0.7,
        val_ratio: 0.15,
      })
      if (res.statuscode === 201 && res.data) {
        setGenerationSummary({
          count: res.data.generated_count,
          splits: res.data.splits_summary,
          levels: res.data.levels_summary,
        })
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error generando dataset sintético."
      setErrorMessage(msg)
    } finally {
      setIsGenerating(false)
    }
  }

  const handleTrainModel = async () => {
    setIsTraining(true)
    setErrorMessage(null)
    setTrainingMessage(null)
    try {
      const res = await footballValidationApi.trainLevelModel({
        version_tag: versionTag.trim() || undefined,
        activate: autoActivate,
      })
      if (res.statuscode === 200 && res.data) {
        setTrainingMessage(
          `¡Entrenamiento exitoso! Modelo versión ${res.data.version} exportado en ONNX y ${
            res.data.activa ? "activado para producción" : "guardado en catálogo"
          }.`
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

  return (
    <div className="space-y-6">
      {/* Top Banner Context */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 rounded-xl border border-border/70 bg-card/60 backdrop-blur-sm">
        <div>
          <div className="flex items-center gap-2">
            <BrainCircuit className="w-6 h-6 text-emerald-500" />
            <h2 className="text-xl font-bold tracking-tight">
              Estudio de Entrenamiento de IA — Fútbol
            </h2>
            <Badge variant="outline" className="text-xs bg-emerald-500/10 text-emerald-600 border-emerald-500/30">
              Garage S3 + ONNX
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Generá datasets de dominadas con física y visión por computadora, entrená modelos locales multinomiales con partición estricta y activá versiones en producción para el Validador.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="flex items-center gap-1.5 py-1 px-3">
            <Cloud className="w-3.5 h-3.5 text-sky-500" />
            Garage S3 (Coolify)
          </Badge>
          <Badge variant="secondary" className="flex items-center gap-1.5 py-1 px-3">
            <Cpu className="w-3.5 h-3.5 text-violet-500" />
            Cero APIs de Terceros
          </Badge>
        </div>
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

      {/* Main Grid: Generador de Dataset & Lanzador de Entrenamiento */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Columna Izquierda: Generador de Muestras Sintéticas */}
        <div className="lg:col-span-5 space-y-6">
          <Card className="border-border/60 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-amber-500" />
                1. Generador de Muestras Sintéticas
              </CardTitle>
              <CardDescription>
                Simula clips reales de dominadas con física parabólica, impactos sonoros, ruido y variabilidad de niveles para entrenar al instante sin esperar grabaciones de campo.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <Label htmlFor="synth-count">Cantidad de Muestras a Generar</Label>
                  <span className="font-semibold text-emerald-600">{synthCount} clips</span>
                </div>
                <Input
                  id="synth-count"
                  type="number"
                  min={1}
                  max={48}
                  value={synthCount}
                  onChange={(e) => setSynthCount(Math.max(1, Math.min(48, Number(e.target.value) || 1)))}
                  className="font-mono text-sm"
                />
                <p className="text-xs text-muted-foreground">
                  Partición automática: 70% Train (entrenamiento), 15% Val (validación), 15% Test (prueba ciega sin fuga).
                </p>
              </div>

              <Button
                onClick={handleGenerateSynthetic}
                disabled={isGenerating}
                className="w-full bg-emerald-600 hover:bg-emerald-700 text-white flex items-center justify-center gap-2 shadow-sm"
              >
                {isGenerating ? (
                  <>
                    <RotateCw className="w-4 h-4 animate-spin" />
                    Generando y subiendo a Garage S3...
                  </>
                ) : (
                  <>
                    <Database className="w-4 h-4" />
                    Generar Muestras y Guardar en S3
                  </>
                )}
              </Button>

              {generationSummary && (
                <div className="p-3 rounded-lg border border-emerald-500/30 bg-emerald-500/5 space-y-2 text-xs">
                  <div className="flex items-center justify-between font-medium text-emerald-700 dark:text-emerald-400">
                    <span>Muestras creadas con éxito:</span>
                    <Badge variant="outline" className="border-emerald-500/40 text-emerald-600">
                      +{generationSummary.count} clips
                    </Badge>
                  </div>
                  <div className="grid grid-cols-3 gap-1 pt-1 text-muted-foreground text-center">
                    <div className="p-1 rounded bg-background/50 border border-border/40">
                      <div className="font-semibold text-foreground">{generationSummary.splits.train || 0}</div>
                      <div>Train</div>
                    </div>
                    <div className="p-1 rounded bg-background/50 border border-border/40">
                      <div className="font-semibold text-foreground">{generationSummary.splits.val || 0}</div>
                      <div>Val</div>
                    </div>
                    <div className="p-1 rounded bg-background/50 border border-border/40">
                      <div className="font-semibold text-foreground">{generationSummary.splits.test || 0}</div>
                      <div>Test</div>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Card Lanzador de Entrenamiento */}
          <Card className="border-border/60 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Play className="w-4 h-4 text-emerald-500" />
                2. Lanzar Entrenamiento de Modelo
              </CardTitle>
              <CardDescription>
                Ajusta los hiperparámetros L2 sobre las 9 características multi-modales, evalúa contra la línea base de reglas y exporta a ONNX.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="version-tag" className="text-sm">
                  Etiqueta de Versión (Opcional)
                </Label>
                <Input
                  id="version-tag"
                  placeholder="ej. 1.2.0 (se auto-asigna si se omite)"
                  value={versionTag}
                  onChange={(e) => setVersionTag(e.target.value)}
                  className="font-mono text-sm"
                />
              </div>

              <div className="flex items-center justify-between p-3 rounded-lg border border-border/50 bg-muted/20">
                <div className="space-y-0.5">
                  <Label htmlFor="auto-activate" className="text-sm font-medium">
                    Activar en Producción
                  </Label>
                  <p className="text-xs text-muted-foreground">
                    El Validador en vivo usará este modelo inmediatamente.
                  </p>
                </div>
                <Switch
                  id="auto-activate"
                  checked={autoActivate}
                  onCheckedChange={setAutoActivate}
                />
              </div>

              <Button
                onClick={handleTrainModel}
                disabled={isTraining}
                className="w-full bg-primary hover:bg-primary/90 text-primary-foreground flex items-center justify-center gap-2"
              >
                {isTraining ? (
                  <>
                    <RotateCw className="w-4 h-4 animate-spin" />
                    Entrenando y Evaluando...
                  </>
                ) : (
                  <>
                    <Cpu className="w-4 h-4" />
                    Entrenar y Exportar ONNX
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
                    Métricas del Modelo: {selectedModel?.version || "Sin versión seleccionada"}
                  </CardTitle>
                  <CardDescription>
                    Evaluado en participantes completamente inéditos (Zero Participant Leakage).
                  </CardDescription>
                </div>
                {selectedModel?.activa && (
                  <Badge className="bg-emerald-600 text-white text-xs">
                    Activo en Producción
                  </Badge>
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
                        {metrics.test_samples || 0}
                      </div>
                      <div className="text-xs text-muted-foreground mt-0.5">Muestras de Test</div>
                    </div>
                  </div>

                  {/* Comparativa con línea base */}
                  {metrics.beats_rule_baseline && (
                    <div className="flex items-center gap-2 p-2.5 rounded-lg border border-emerald-500/30 bg-emerald-500/5 text-xs text-emerald-700 dark:text-emerald-400">
                      <CheckCircle2 className="w-4 h-4 shrink-0" />
                      <span>
                        El modelo entrenado supera a la línea base de reglas (
                        {((metrics.trained_exact_accuracy || 0) * 100).toFixed(1)}% vs{" "}
                        {((metrics.rule_baseline_accuracy || 0) * 100).toFixed(1)}%).
                      </span>
                    </div>
                  )}

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
                      <div className="text-xs font-semibold text-muted-foreground">
                        Convergencia de Pérdida (Cross-Entropy Loss por Épocas)
                      </div>
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
                  {isLoadingModels
                    ? "Cargando versiones de modelo..."
                    : "No hay métricas disponibles. Lanzá un entrenamiento para generar el primer modelo."}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Tabla de Versiones de Modelos */}
      <Card className="border-border/60 shadow-sm">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <Layers className="w-4 h-4 text-emerald-500" />
              Versiones de Modelos en Base de Datos (`model_versions`)
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
          <CardDescription>
            Control de versiones de los artefactos ONNX y activación para el Validador de producción sin reiniciar el servidor.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {models.length === 0 ? (
            <div className="py-8 text-center text-muted-foreground text-sm">
              No hay versiones registradas aún. Generá muestras y lanzá un entrenamiento para crear la primera versión.
            </div>
          ) : (
            <div className="overflow-x-auto border border-border/60 rounded-lg">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Versión</TableHead>
                    <TableHead>Estado</TableHead>
                    <TableHead>Exact Accuracy</TableHead>
                    <TableHead>±1 Nivel</TableHead>
                    <TableHead>Almacenamiento</TableHead>
                    <TableHead className="text-right">Acción</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {models.map((m) => {
                    const isSelected = selectedModel?.id === m.id
                    return (
                      <TableRow
                        key={m.id}
                        className={`cursor-pointer ${isSelected ? "bg-muted/40" : ""}`}
                        onClick={() => setSelectedModel(m)}
                      >
                        <TableCell className="font-mono font-medium">
                          {m.version}
                        </TableCell>
                        <TableCell>
                          {m.activa ? (
                            <Badge className="bg-emerald-600 text-white text-[11px]">
                              Activo
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="text-muted-foreground text-[11px]">
                              Inactivo
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell className="font-medium text-emerald-600">
                          {m.metricas.trained_exact_accuracy
                            ? `${(m.metricas.trained_exact_accuracy * 100).toFixed(1)}%`
                            : "—"}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {m.metricas.trained_within_one_level_accuracy
                            ? `${(m.metricas.trained_within_one_level_accuracy * 100).toFixed(1)}%`
                            : "—"}
                        </TableCell>
                        <TableCell className="font-mono text-xs text-muted-foreground max-w-xs truncate">
                          {m.ruta_onnx}
                        </TableCell>
                        <TableCell className="text-right">
                          {m.activa ? (
                            <span className="text-xs text-emerald-600 font-medium">En uso</span>
                          ) : (
                            <Button
                              variant="outline"
                              size="sm"
                              className="h-7 text-xs text-emerald-600 hover:text-emerald-700"
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

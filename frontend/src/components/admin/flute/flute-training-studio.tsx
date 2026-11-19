import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import {
  activateFluteModel, getFluteDatasetPreview, listFluteModels, trainFluteModel,
  type FluteDatasetPreviewResponse, type FluteModelVersionItem,
} from "@/services/dataset-sample-service"

import { FluteVideoReprocessor } from "./flute-video-reprocessor"
import { FLUTE_VISUAL_SCHEMA } from "./flute-hand-features"

interface FluteTrainingStudioProps { skillId?: string; skillName?: string }
const percent = (value: number | null | undefined) => value == null ? "No verificada" : `${(value * 100).toFixed(1)}%`

export function FluteTrainingStudio({ skillId, skillName = "Flauta Dulce" }: FluteTrainingStudioProps) {
  const [models, setModels] = useState<FluteModelVersionItem[]>([])
  const [selected, setSelected] = useState<FluteModelVersionItem | null>(null)
  const [preview, setPreview] = useState<FluteDatasetPreviewResponse | null>(null)
  const [versionTag, setVersionTag] = useState("")
  const [activate, setActivate] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const refresh = async () => {
    const [versions, coverage] = await Promise.all([listFluteModels(), getFluteDatasetPreview()])
    setModels(versions.data ?? [])
    setSelected(versions.data?.find(m => m.activa) ?? versions.data?.[0] ?? null)
    setPreview(coverage.data)
  }
  const perform = async (action: () => Promise<void>) => {
    setBusy(true)
    setError(null)
    try { await action() } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error en el estudio de flauta.")
    } finally { setBusy(false) }
  }
  useEffect(() => { void perform(refresh) }, [])
  const metrics = selected?.metricas

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">Estudio de Entrenamiento — {skillName}</h2>
      <p className="text-sm text-muted-foreground">Dos cabezas ONNX: sonido (11 notas + NO_FLAUTA) y digitación (11 notas + INCORRECTA).</p>
      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
      {message && <Alert><AlertDescription>{message}</AlertDescription></Alert>}
      <Card>
        <CardHeader><CardTitle>Cobertura de etiquetas</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <p>{preview?.labeled_count ?? 0} etiquetadas / {preview?.total_count ?? 0} muestras · {preview?.unlabeled_count ?? 0} pendientes · {Object.keys(preview?.participants ?? {}).length} participantes</p>
          <Alert variant={preview?.can_validate_independently ? "default" : "destructive"}>
            <AlertDescription>{preview?.can_validate_independently
              ? "Hay participantes suficientes para intentar una partición independiente. Consulta la validación del modelo después de entrenar."
              : "Validación independiente no disponible: etiqueta muestras de al menos dos personas con IDs estables."}</AlertDescription>
          </Alert>
          {(["sound_class_counts", "posture_class_counts"] as const).map(key => (
            <div key={key} className="space-y-2">
              <h3 className="font-medium">{key === "sound_class_counts" ? "Sonido" : "Digitación"} · fotogramas etiquetados</h3>
              <div className="flex flex-wrap gap-2">{Object.entries(preview?.[key] ?? {}).map(([label, count]) => <Badge key={label} variant="outline">{label}: {count}</Badge>)}</div>
            </div>
          ))}
          <Button disabled={busy} variant="outline" onClick={() => void perform(refresh)}>Actualizar cobertura</Button>
        </CardContent>
      </Card>
      <FluteVideoReprocessor samples={preview?.samples ?? []} onSaved={refresh} />
      <Card>
        <CardHeader><CardTitle>Entrenar modelo</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <Label htmlFor="flute-version">Versión opcional</Label>
          <Input id="flute-version" value={versionTag} onChange={e => setVersionTag(e.target.value)} />
          <div className="flex items-center gap-2"><Switch id="flute-activate" checked={activate} onCheckedChange={setActivate} /><Label htmlFor="flute-activate">Activar para inferencia</Label></div>
          <Button disabled={busy} onClick={() => void perform(async () => {
            const res = await trainFluteModel({ version_tag: versionTag.trim() || undefined, activate, skill_id: skillId })
            setMessage(res.message)
            await refresh()
          })}>{busy ? "Procesando…" : "Entrenar ONNX"}</Button>
        </CardContent>
      </Card>
      <div className="flex flex-wrap gap-2">
        {models.map(model => <Button key={model.id} variant={selected?.id === model.id ? "default" : "outline"} onClick={() => setSelected(model)}>{model.version}{model.activa ? " · Activo" : ""}</Button>)}
      </div>
      {selected && metrics && <Card>
        <CardHeader><CardTitle>Métricas — {selected.version}</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <Alert variant={metrics.validated ? "default" : "destructive"}><AlertDescription>{metrics.validation_note || "Validación independiente no verificada."}</AlertDescription></Alert>
          {metrics.visual_schema !== FLUTE_VISUAL_SCHEMA && <Alert variant="destructive"><AlertDescription>Modelo de cuadrícula antigua: reprocesa los videos y entrena una versión con articulaciones antes de usar el validador.</AlertDescription></Alert>}
          <p>Entrenamiento: {metrics.train_samples ?? "—"} · Prueba: {metrics.test_samples ?? "—"} {metrics.metric_unit === "feature_frame" ? "fotogramas (no personas independientes)" : "muestras"} · Latencia: {metrics.latency_ms_per_inference ?? "—"} ms</p>
          {(["sound", "posture"] as const).map(key => {
            const head = metrics[key]
            if (!head) return <p key={key}>Modelo antiguo sin métricas duales; vuelve a entrenar.</p>
            return <section key={key} className="space-y-2">
              <h3 className="font-semibold">{key === "sound" ? "Sonido" : "Digitación / postura"}</h3>
              <p>Exactitud: {percent(head.test_accuracy)} · Línea base {key === "sound" ? "acústica" : "mayoritaria"}: {percent(head.rule_baseline_accuracy ?? head.majority_baseline_accuracy)}</p>
              <p className="text-xs text-muted-foreground">Matriz de confusión: filas reales, columnas predichas.</p>
              <div className="overflow-x-auto"><Table>
                <TableHeader><TableRow><TableHead>Real / Predicha</TableHead>{head.classes.map(label => <TableHead key={label}>{label}</TableHead>)}</TableRow></TableHeader>
                <TableBody>{head.confusion_matrix.map((row, i) => <TableRow key={head.classes[i]}><TableCell>{head.classes[i]}</TableCell>{row.map((count, j) => <TableCell key={j}>{count}</TableCell>)}</TableRow>)}</TableBody>
              </Table></div>
            </section>
          })}
          {!selected.activa && <Button disabled={busy} onClick={() => void perform(async () => { const res = await activateFluteModel(selected.id); setMessage(res.message); await refresh() })}>Activar versión</Button>}
        </CardContent>
      </Card>}
    </div>
  )
}

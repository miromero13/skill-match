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
import { fluteSplitModeLabel, isLegacyFluteModel } from "./flute-live-scoring"

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
      <p className="text-sm text-muted-foreground">Modelo dual ONNX (MLP): sonido con altura primero (la frecuencia detectada decide la nota y el timbre confirma flauta o NO_FLAUTA) y digitación multi-etiqueta por dedo (7 huecos frontales tapado/destapado; el pulgar trasero no es evaluable por cámara).</p>
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
          {(["sound_class_counts", "finger_note_counts"] as const).map(key => (
            <div key={key} className="space-y-2">
              <h3 className="font-medium">{key === "sound_class_counts" ? "Sonido" : "Digitación correcta"} · fotogramas etiquetados</h3>
              <div className="flex flex-wrap gap-2">{Object.entries(preview?.[key] ?? {}).map(([label, count]) => <Badge key={label} variant="outline">{label}: {count}</Badge>)}</div>
            </div>
          ))}
          {(preview?.needs_reprocess_count ?? 0) > 0 && <Alert variant="destructive"><AlertDescription>{preview?.needs_reprocess_count} video(s) tienen features de un formato anterior: reprocesalos en «Reutilizar videos guardados» para usarlos en el entrenamiento.</AlertDescription></Alert>}
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
          {isLegacyFluteModel(metrics) && <Alert variant="destructive"><AlertDescription>Modelo de formato anterior: reprocesa los videos con el extractor de altura y la nueva lateralidad de manos y entrena una nueva versión antes de usar el validador.</AlertDescription></Alert>}
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={metrics.split_mode === "participant" ? "default" : "outline"}>Partición: {fluteSplitModeLabel(metrics.split_mode)}</Badge>
            <Badge variant="outline">Afinación: {metrics.tuning_offset_cents == null ? "—" : `${metrics.tuning_offset_cents > 0 ? "+" : ""}${metrics.tuning_offset_cents.toFixed(1)} cents`}</Badge>
          </div>
          <p>Entrenamiento: {metrics.train_samples ?? "—"} · Prueba: {metrics.test_samples ?? "—"} {metrics.metric_unit === "feature_frame" ? "fotogramas" : "muestras"} · Latencia: {metrics.latency_ms_per_inference ?? "—"} ms</p>
          {metrics.sound ? <section className="space-y-2">
            <h3 className="font-semibold">Sonido (altura + timbre de flauta)</h3>
            <p>Entrenamiento: {percent(metrics.sound.train_accuracy)} · Prueba (fotogramas): {percent(metrics.sound.test_accuracy)} · Prueba por toma: {percent(metrics.sound.sample_test_accuracy)} · Línea base mayoritaria: {percent(metrics.sound.majority_baseline_accuracy)}</p>
            {metrics.sound.per_class && <div className="overflow-x-auto"><Table>
              <TableHeader><TableRow><TableHead>Clase</TableHead><TableHead>Precisión</TableHead><TableHead>Recall</TableHead><TableHead>Soporte</TableHead></TableRow></TableHeader>
              <TableBody>{Object.entries(metrics.sound.per_class).map(([label, report]) => <TableRow key={label}><TableCell>{label}</TableCell><TableCell>{percent(report.precision)}</TableCell><TableCell>{percent(report.recall)}</TableCell><TableCell>{report.support}</TableCell></TableRow>)}</TableBody>
            </Table></div>}
            {metrics.sound.per_participant && Object.keys(metrics.sound.per_participant).length > 0 && <div className="flex flex-wrap gap-2">{Object.entries(metrics.sound.per_participant).map(([participant, accuracy]) => <Badge key={participant} variant="outline">{participant}: {percent(accuracy)}</Badge>)}</div>}
            <p className="text-xs text-muted-foreground">Matriz de confusión por toma: filas reales, columnas predichas.</p>
            <div className="overflow-x-auto"><Table>
              <TableHeader><TableRow><TableHead>Real / Predicha</TableHead>{metrics.sound.classes.map(label => <TableHead key={label}>{label}</TableHead>)}</TableRow></TableHeader>
              <TableBody>{metrics.sound.confusion_matrix.map((row, i) => <TableRow key={metrics.sound.classes[i]}><TableCell>{metrics.sound.classes[i]}</TableCell>{row.map((count, j) => <TableCell key={j}>{count}</TableCell>)}</TableRow>)}</TableBody>
            </Table></div>
          </section> : <p>Modelo antiguo sin métricas de sonido; vuelve a entrenar.</p>}
          {metrics.fingers ? <section className="space-y-2">
            <h3 className="font-semibold">Digitación por dedo (7 huecos frontales)</h3>
            <p>Entrenamiento: {percent(metrics.fingers.train_accuracy)} · Prueba (media por hueco): {percent(metrics.fingers.test_accuracy)} · Tomas con digitación completa: {percent(metrics.fingers.sample_test_accuracy)} · Línea base mayoritaria: {percent(metrics.fingers.majority_baseline_accuracy)} · {metrics.fingers.train_frames} fotogramas</p>
            <div className="overflow-x-auto"><Table>
              <TableHeader><TableRow><TableHead>Hueco</TableHead><TableHead>Mano</TableHead><TableHead>Prueba</TableHead><TableHead>Línea base</TableHead></TableRow></TableHeader>
              <TableBody>{metrics.fingers.per_hole.map(row => <TableRow key={row.hole}><TableCell>{row.hole}</TableCell><TableCell>{row.hole <= 3 ? "Izquierda" : "Derecha"}</TableCell><TableCell>{percent(row.test_accuracy)}</TableCell><TableCell>{percent(row.baseline)}</TableCell></TableRow>)}</TableBody>
            </Table></div>
            <p className="text-xs text-muted-foreground">Pulgar trasero: no evaluable por cámara.</p>
          </section> : <p>Modelo antiguo sin métricas por dedo; vuelve a entrenar.</p>}
          {!selected.activa && <Button disabled={busy} onClick={() => void perform(async () => { const res = await activateFluteModel(selected.id); setMessage(res.message); await refresh() })}>Activar versión</Button>}
        </CardContent>
      </Card>}
    </div>
  )
}

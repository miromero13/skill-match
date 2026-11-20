import { Film, Layers, ListChecks } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { MetricTypeInfo } from "@/types/catalog"
import { formatPercent, metricTypeLabel } from "../lib/skill-lab-utils"
import type { SkillLabLevel, SkillLabSample } from "../types"
import { ReferenceUploader } from "./reference-uploader"
import { TrainingSampleList } from "./training-sample-list"
import { TrainingUploader } from "./training-uploader"

interface LevelCardProps {
  skillId: string
  level: SkillLabLevel
  samples: SkillLabSample[]
  metricTypes: MetricTypeInfo[]
  onChanged: () => void | Promise<void>
}

export function LevelCard({ skillId, level, samples, metricTypes, onChanged }: LevelCardProps) {
  const trainingSamples = samples.filter(
    (sample) => sample.skill_level_id === level.id && sample.sample_role === "TRAINING"
  )

  return (
    <Card className="border-border/60 shadow-sm" data-testid={`skill-lab-level-${level.id}`}>
      <CardHeader className="pb-3">
        <CardTitle className="flex flex-wrap items-center gap-2 text-base font-semibold">
          <Layers className="size-4 text-emerald-500" />
          <span>
            Nivel {level.level_number} · {level.name}
          </span>
          <Badge variant="outline">{`Puntaje mínimo ${formatPercent(level.min_score)}%`}</Badge>
          <Badge variant="secondary">{`${level.training_samples} videos de entrenamiento`}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <section aria-labelledby={`level-criteria-heading-${level.id}`} className="space-y-2">
          <h3
            id={`level-criteria-heading-${level.id}`}
            className="flex items-center gap-1.5 text-sm font-semibold text-foreground"
          >
            <ListChecks className="size-4 text-emerald-500" />
            Criterios de evaluación
          </h3>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Criterio</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead className="text-right">Peso</TableHead>
                <TableHead className="text-right">Objetivo</TableHead>
                <TableHead className="text-right">Videos de entrenamiento</TableHead>
                <TableHead>Referencia</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {level.criteria.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-xs whitespace-normal text-muted-foreground">
                    Sin criterios: el nivel se evalúa como replicación del video de referencia (100%).
                  </TableCell>
                </TableRow>
              ) : (
                level.criteria.map((criterion) => (
                  <TableRow key={criterion.key}>
                    <TableCell className="font-medium whitespace-normal">{criterion.name}</TableCell>
                    <TableCell className="whitespace-normal">
                      {metricTypeLabel(metricTypes, criterion.metric_type)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{`${formatPercent(criterion.weight)}%`}</TableCell>
                    <TableCell className="text-right tabular-nums">{criterion.target ?? "—"}</TableCell>
                    <TableCell className="text-right tabular-nums">{criterion.training_samples}</TableCell>
                    <TableCell>{criterion.has_reference ? "Sí" : "No"}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </section>

        {/* Referencia y entrenamiento en dos secciones: lado a lado desde lg, apiladas debajo. */}
        <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
          <ReferenceUploader skillId={skillId} level={level} samples={samples} onChanged={onChanged} />
          <section
            aria-labelledby={`level-training-heading-${level.id}`}
            className="space-y-3 rounded-lg border border-border/60 p-3 sm:p-4"
          >
            <div className="space-y-0.5">
              <h3
                id={`level-training-heading-${level.id}`}
                className="flex items-center gap-1.5 text-sm font-semibold text-foreground"
              >
                <Film className="size-4 text-emerald-500" />
                Videos de entrenamiento
              </h3>
              <p className="text-xs text-muted-foreground">
                Ejemplos etiquetados de este nivel para calibrar el modelo.
              </p>
            </div>
            <TrainingUploader skillId={skillId} level={level} onChanged={onChanged} />
            <TrainingSampleList level={level} samples={trainingSamples} onChanged={onChanged} />
          </section>
        </div>
      </CardContent>
    </Card>
  )
}

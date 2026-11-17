import {
  RotateCcw,
  SlidersHorizontal,
  ShieldCheck,
  MapPin,
  Globe,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Slider } from "@/components/ui/slider"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useTutorSearchStore } from "@/stores/search-store"

interface SearchFilterPanelProps {
  className?: string
  onClose?: () => void
}

export function SearchFilterPanel({ className, onClose }: SearchFilterPanelProps) {
  const {
    filters,
    categories,
    setFilter,
    resetFilters,
  } = useTutorSearchStore()

  const handleReset = () => {
    resetFilters()
    onClose?.()
  }

  return (
    <div className={`space-y-6 ${className || ""}`}>
      {/* Encabezado del panel de filtros */}
      <div className="flex items-center justify-between border-b pb-3">
        <div className="flex items-center gap-2">
          <SlidersHorizontal className="h-4 w-4 text-primary" />
          <h2 className="font-semibold text-sm text-foreground">Filtros Avanzados</h2>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="h-8 px-2 text-xs text-muted-foreground hover:text-foreground gap-1"
          onClick={handleReset}
        >
          <RotateCcw className="h-3 w-3" />
          <span>Limpiar</span>
        </Button>
      </div>

      {/* 1. Toggle Verificado por IA (RF-MAT-11) */}
      <div className="flex items-center justify-between rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3">
        <div className="space-y-0.5 pr-2">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-800 dark:text-emerald-300">
            <ShieldCheck className="h-4 w-4 text-emerald-600 shrink-0" />
            <span>Solo verificados por IA</span>
          </div>
          <p className="text-[11px] text-muted-foreground">
            Instructores con habilidades validadas por modelos de IA propios.
          </p>
        </div>
        <Switch
          checked={Boolean(filters.verified_only)}
          onCheckedChange={(checked) => setFilter("verified_only", checked)}
          aria-label="Filtrar solo instructores verificados por IA"
        />
      </div>

      {/* 2. Criterio de ordenamiento */}
      <div className="space-y-2">
        <Label className="text-xs font-medium">Ordenar por</Label>
        <Select
          value={filters.sort_by || "reputation"}
          onValueChange={(val) =>
            setFilter(
              "sort_by",
              val as "reputation" | "distance" | "points_asc" | "points_desc" | "experience" | "recent"
            )
          }
        >
          <SelectTrigger className="h-9 text-xs">
            <SelectValue placeholder="Ordenar por" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="reputation">Compatibilidad y Reputación</SelectItem>
            <SelectItem value="distance">Cercanía geográfica</SelectItem>
            <SelectItem value="points_asc">Menor tarifa en puntos</SelectItem>
            <SelectItem value="points_desc">Mayor tarifa en puntos</SelectItem>
            <SelectItem value="experience">Mayor experiencia</SelectItem>
            <SelectItem value="recent">Nuevos instructores</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* 3. Categoría */}
      <div className="space-y-2">
        <Label className="text-xs font-medium">Categoría disciplinar</Label>
        <Select
          value={filters.category_id || "all"}
          onValueChange={(val) => setFilter("category_id", val === "all" ? "" : val)}
        >
          <SelectTrigger className="h-9 text-xs">
            <SelectValue placeholder="Todas las categorías" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todas las categorías</SelectItem>
            {categories.map((c) => (
              <SelectItem key={c.id} value={c.id}>
                {c.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* 4. Modalidad de enseñanza */}
      <div className="space-y-2">
        <Label className="text-xs font-medium">Modalidad</Label>
        <div className="grid grid-cols-3 gap-1.5">
          <Button
            type="button"
            variant={filters.modality === undefined ? "default" : "outline"}
            size="sm"
            className="h-8 text-[11px] px-1"
            onClick={() => setFilter("modality", undefined)}
          >
            Todas
          </Button>
          <Button
            type="button"
            variant={filters.modality === "VIRTUAL" ? "default" : "outline"}
            size="sm"
            className="h-8 text-[11px] px-1 gap-1"
            onClick={() => setFilter("modality", "VIRTUAL")}
          >
            <Globe className="h-3 w-3" />
            Virtual
          </Button>
          <Button
            type="button"
            variant={filters.modality === "PRESENCIAL" ? "default" : "outline"}
            size="sm"
            className="h-8 text-[11px] px-1 gap-1"
            onClick={() => setFilter("modality", "PRESENCIAL")}
          >
            <MapPin className="h-3 w-3" />
            Presencial
          </Button>
        </div>
      </div>

      {/* 5. Radio de distancia geográfica (Slider) */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs">
          <Label className="font-medium">Radio geográfico máximo</Label>
          <span className="font-semibold text-primary">
            {filters.max_distance && filters.max_distance > 0
              ? `${filters.max_distance} km`
              : "Sin límite"}
          </span>
        </div>
        <Slider
          value={[filters.max_distance || 0]}
          min={0}
          max={100}
          step={5}
          onValueChange={(val) => {
            const num = val[0]
            setFilter("max_distance", num === 0 ? undefined : num)
          }}
          className="py-2"
        />
        <div className="flex justify-between text-[10px] text-muted-foreground">
          <span>0 km (Todos)</span>
          <span>50 km</span>
          <span>100 km</span>
        </div>
      </div>

      {/* 6. Nivel mínimo de destreza */}
      <div className="space-y-2">
        <Label className="text-xs font-medium">Nivel mínimo de enseñanza</Label>
        <Select
          value={filters.min_level || "all"}
          onValueChange={(val) => setFilter("min_level", val === "all" ? "" : val)}
        >
          <SelectTrigger className="h-9 text-xs">
            <SelectValue placeholder="Cualquier nivel" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Cualquier nivel</SelectItem>
            <SelectItem value="BEGINNER">Principiante (1+)</SelectItem>
            <SelectItem value="INTERMEDIATE">Intermedio (2+)</SelectItem>
            <SelectItem value="ADVANCED">Avanzado (3+)</SelectItem>
            <SelectItem value="EXPERT">Experto (4)</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {onClose && (
        <div className="pt-2">
          <Button className="w-full text-xs h-9" onClick={onClose}>
            Aplicar Filtros
          </Button>
        </div>
      )}
    </div>
  )
}

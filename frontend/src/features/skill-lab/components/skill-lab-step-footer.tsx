import { Link } from "react-router-dom"
import { ArrowLeft, ChevronLeft, ChevronRight } from "lucide-react"
import { Button } from "@/components/ui/button"

interface SkillLabStepFooterProps {
  /** Paso actual, 1-based. */
  current: number
  total: number
  /** Nombre del paso siguiente; `null` en el último paso. */
  nextTitle: string | null
  onPrevious: () => void
  onNext: () => void
}

/**
 * Barra "Anterior / Siguiente" (S8). En móvil y tablet queda fija sobre la barra inferior del layout admin
 * (≈53 px + safe area, visible por debajo de `lg`); en escritorio flota al pie del contenido.
 */
export function SkillLabStepFooter({ current, total, nextTitle, onPrevious, onNext }: SkillLabStepFooterProps) {
  return (
    <div
      data-testid="skill-lab-step-footer"
      className="sticky bottom-[calc(3.75rem+env(safe-area-inset-bottom))] z-30 flex items-center justify-between gap-2 rounded-xl border border-border/60 bg-background/95 p-2 shadow-lg backdrop-blur-md supports-[backdrop-filter]:bg-background/80 sm:p-3 lg:bottom-4"
    >
      <Button type="button" variant="outline" onClick={onPrevious} disabled={current <= 1}>
        <ChevronLeft />
        Anterior
      </Button>
      <span className="hidden text-xs text-muted-foreground tabular-nums sm:inline">{`${current}/${total}`}</span>
      {nextTitle ? (
        <Button
          type="button"
          onClick={onNext}
          aria-label={`Siguiente: ${nextTitle}`}
          title={nextTitle}
          className="min-w-0 max-w-[70%] sm:max-w-sm"
        >
          Siguiente
          <ChevronRight />
        </Button>
      ) : (
        <Button asChild>
          <Link to="/admin/catalog">
            <ArrowLeft />
            Volver al catálogo
          </Link>
        </Button>
      )}
    </div>
  )
}

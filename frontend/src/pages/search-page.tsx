import { useEffect, useState } from "react"
import {
  Search,
  X,
  Compass,
  RotateCcw,
  ShieldCheck,
  ChevronLeft,
  ChevronRight,
  Frown,
} from "lucide-react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { TutorCard } from "@/components/search/tutor-card"
import { SearchFilterPanel } from "@/components/search/search-filter-panel"
import { MobileFilterDrawer } from "@/components/search/mobile-filter-drawer"
import { ProposalDialog } from "@/components/search/proposal-dialog"
import { useTutorSearchStore } from "@/stores/search-store"
import type { TutorSearchResult } from "@/types/search"

export function SearchPage() {
  const {
    filters,
    tutors,
    totalCount,
    isLoading,
    apiMessage,
    setFilter,
    resetFilters,
    fetchTutors,
    fetchCatalogData,
  } = useTutorSearchStore()

  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false)
  const [selectedTutor, setSelectedTutor] = useState<TutorSearchResult | null>(null)
  const [proposalOpen, setProposalOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState(filters.query || "")

  useEffect(() => {
    fetchCatalogData()
    fetchTutors()
  }, [fetchCatalogData, fetchTutors])

  // Sincronizar input local de búsqueda
  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setFilter("query", searchTerm)
  }

  const handleClearQuery = () => {
    setSearchTerm("")
    setFilter("query", "")
  }

  const handleProposeSwap = (tutor: TutorSearchResult) => {
    setSelectedTutor(tutor)
    setProposalOpen(true)
  }

  // Contar filtros activos
  const activeFiltersCount = [
    Boolean(filters.query),
    Boolean(filters.category_id),
    Boolean(filters.min_level),
    Boolean(filters.verified_only),
    Boolean(filters.modality),
    Boolean(filters.max_distance && filters.max_distance > 0),
  ].filter(Boolean).length

  const currentPage = filters.page || 1
  const pageSize = filters.page_size || 12
  const totalPages = Math.ceil(totalCount / pageSize) || 1

  return (
    <div className="mx-auto w-full max-w-7xl p-4 sm:p-6 lg:p-8 space-y-6">
      {/* 1. Header principal y Barra de Búsqueda Superior */}
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <Compass className="h-6 w-6 text-primary" />
              <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
                Explorar Instructores
              </h1>
            </div>
            <p className="text-xs sm:text-sm text-muted-foreground mt-1">
              Encuentra miembros de la comunidad para intercambio directo de habilidades o pago con puntos.
            </p>
          </div>

          {/* Botón de filtros móvil */}
          <MobileFilterDrawer
            open={mobileDrawerOpen}
            onOpenChange={setMobileDrawerOpen}
            activeFiltersCount={activeFiltersCount}
          />
        </div>

        {/* Buscador interactivo */}
        <form onSubmit={handleSearchSubmit} className="flex gap-2 items-center">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Buscar por instructor, habilidad (ej. Python, Guitarra) o palabra clave..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9 pr-9 h-11 text-xs sm:text-sm bg-background border-border/80 focus-visible:ring-primary shadow-xs"
            />
            {searchTerm && (
              <button
                type="button"
                onClick={handleClearQuery}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-1"
                aria-label="Limpiar búsqueda"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
          <Button type="submit" className="h-11 px-5 text-xs sm:text-sm font-semibold">
            Buscar
          </Button>
        </form>

        {/* Quick filters pills para móvil y desktop */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1 text-xs">
          <span className="text-[11px] text-muted-foreground shrink-0 font-medium">Accesos rápidos:</span>
          <Badge
            variant={filters.verified_only ? "default" : "outline"}
            className="cursor-pointer gap-1 shrink-0 select-none py-1 px-2.5"
            onClick={() => setFilter("verified_only", !filters.verified_only)}
          >
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
            Solo Verificados IA
          </Badge>

          <Badge
            variant={filters.modality === "VIRTUAL" ? "default" : "outline"}
            className="cursor-pointer shrink-0 select-none py-1 px-2.5"
            onClick={() => setFilter("modality", filters.modality === "VIRTUAL" ? undefined : "VIRTUAL")}
          >
            Virtual
          </Badge>

          <Badge
            variant={filters.modality === "PRESENCIAL" ? "default" : "outline"}
            className="cursor-pointer shrink-0 select-none py-1 px-2.5"
            onClick={() => setFilter("modality", filters.modality === "PRESENCIAL" ? undefined : "PRESENCIAL")}
          >
            Presencial
          </Badge>

          {activeFiltersCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 text-[11px] px-2 text-muted-foreground gap-1"
              onClick={resetFilters}
            >
              <RotateCcw className="h-3 w-3" />
              Restablecer ({activeFiltersCount})
            </Button>
          )}
        </div>
      </div>

      {/* 2. Cuerpo de Búsqueda: Panel lateral (Desktop) + Feed de Resultados */}
      <div className="flex flex-col lg:flex-row gap-6 items-start">
        {/* Panel lateral de filtros en Desktop */}
        <aside className="hidden lg:block w-72 shrink-0 rounded-xl border bg-card p-5 shadow-xs sticky top-20">
          <SearchFilterPanel />
        </aside>

        {/* Feed de Resultados */}
        <main className="flex-1 min-w-0 w-full space-y-4">
          {/* Barra de estado de resultados */}
          <div className="flex items-center justify-between border-b pb-3 text-xs sm:text-sm">
            <span className="font-medium text-foreground">
              {isLoading ? (
                "Buscando instructores compatibles..."
              ) : (
                apiMessage || `Se encontraron ${totalCount} instructores compatibles.`
              )}
            </span>
            <span className="text-xs text-muted-foreground">
              Página {currentPage} de {totalPages}
            </span>
          </div>

          {/* Grid de tarjetas de instructores */}
          {isLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {[1, 2, 3, 4].map((i) => (
                <Card key={i} className="p-5 space-y-4">
                  <div className="flex items-center gap-3">
                    <Skeleton className="h-12 w-12 rounded-full" />
                    <div className="space-y-2 flex-1">
                      <Skeleton className="h-4 w-1/2" />
                      <Skeleton className="h-3 w-1/3" />
                    </div>
                  </div>
                  <Skeleton className="h-14 w-full rounded-lg" />
                  <div className="flex justify-between items-center pt-2">
                    <Skeleton className="h-4 w-24" />
                    <Skeleton className="h-8 w-28 rounded-md" />
                  </div>
                </Card>
              ))}
            </div>
          ) : tutors.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-xl border border-dashed p-10 text-center space-y-3 bg-card/50">
              <div className="rounded-full bg-muted p-3">
                <Frown className="h-8 w-8 text-muted-foreground" />
              </div>
              <div className="space-y-1">
                <h3 className="font-semibold text-base text-foreground">
                  No se encontraron instructores compatibles
                </h3>
                <p className="text-xs text-muted-foreground max-w-sm">
                  Prueba modificando tus términos de búsqueda, ampliando el radio de distancia o desactivando filtros restrictivos.
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={resetFilters}
                className="gap-1.5 text-xs mt-2"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                <span>Restablecer todos los filtros</span>
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {tutors.map((tutor) => (
                <TutorCard
                  key={tutor.id}
                  tutor={tutor}
                  onProposeSwap={handleProposeSwap}
                />
              ))}
            </div>
          )}

          {/* Paginación */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 pt-6">
              <Button
                variant="outline"
                size="sm"
                disabled={currentPage <= 1 || isLoading}
                onClick={() => setFilter("page", currentPage - 1)}
                className="h-8 text-xs gap-1"
              >
                <ChevronLeft className="h-3.5 w-3.5" />
                Anterior
              </Button>
              <span className="text-xs text-muted-foreground px-2">
                {currentPage} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={currentPage >= totalPages || isLoading}
                onClick={() => setFilter("page", currentPage + 1)}
                className="h-8 text-xs gap-1"
              >
                Siguiente
                <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          )}
        </main>
      </div>

      {/* Modal de Propuesta de Intercambio */}
      <ProposalDialog
        tutor={selectedTutor}
        open={proposalOpen}
        onOpenChange={setProposalOpen}
      />
    </div>
  )
}

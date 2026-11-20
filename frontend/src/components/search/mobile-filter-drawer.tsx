import { SlidersHorizontal } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
import { SearchFilterPanel } from "@/components/search/search-filter-panel"

interface MobileFilterDrawerProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  activeFiltersCount?: number
}

export function MobileFilterDrawer({
  open,
  onOpenChange,
  activeFiltersCount = 0,
}: MobileFilterDrawerProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetTrigger asChild>
        <Button variant="outline" size="sm" className="h-9 gap-1.5 md:hidden text-xs">
          <SlidersHorizontal className="h-4 w-4 text-primary" />
          <span>Filtros</span>
          {activeFiltersCount > 0 && (
            <span className="flex h-4 w-4 items-center justify-center rounded-full bg-primary text-[10px] text-primary-foreground font-bold">
              {activeFiltersCount}
            </span>
          )}
        </Button>
      </SheetTrigger>
      <SheetContent side="right" className="w-[85vw] sm:max-w-md overflow-y-auto p-4 sm:p-6">
        <SheetHeader className="mb-4 text-left">
          <SheetTitle className="text-base font-bold flex items-center gap-2">
            <SlidersHorizontal className="h-4 w-4 text-primary" />
            Filtros Avanzados
          </SheetTitle>
          <SheetDescription className="text-xs text-muted-foreground">
            Ajusta los parámetros para encontrar al instructor idóneo para tu intercambio.
          </SheetDescription>
        </SheetHeader>

        <SearchFilterPanel onClose={() => onOpenChange(false)} />
      </SheetContent>
    </Sheet>
  )
}

import { useState, type ReactNode } from "react"
import { Info } from "lucide-react"
import { cn } from "cn"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"

interface InfoTipProps {
  /** Nombre accesible del botón (p. ej. "Ayuda: video de referencia"). */
  label: string
  children: ReactNode
  className?: string
}

/**
 * Explicación secundaria detrás de un icono de información (S9). Se abre con hover, foco o toque
 * (el toque no dispara hover en móvil, por eso el click la abre explícitamente).
 */
export function InfoTip({ label, children, className }: InfoTipProps) {
  const [open, setOpen] = useState(false)
  return (
    <TooltipProvider>
      <Tooltip open={open} onOpenChange={setOpen}>
        <TooltipTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="icon-xs"
            aria-label={label}
            onClick={(event) => {
              event.preventDefault()
              setOpen(true)
            }}
            className={cn("size-5 text-muted-foreground hover:text-foreground", className)}
          >
            <Info />
          </Button>
        </TooltipTrigger>
        <TooltipContent className="max-w-64 text-pretty">{children}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

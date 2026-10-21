import { Outlet, Link } from "react-router-dom"
import { ShieldCheck, Clock, ArrowLeft } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

export function ExamLayout() {
  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background text-foreground">
      {/* Top Telemetry & Proctoring Bar */}
      <header className="flex h-14 shrink-0 items-center justify-between border-b bg-card px-4 sm:px-6">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" asChild className="h-8 px-2 text-xs">
            <Link to="/app">
              <ArrowLeft className="mr-1 h-3.5 w-3.5" />
              <span>Salir</span>
            </Link>
          </Button>
          <div className="h-4 w-px bg-border" />
          <div className="flex items-center gap-2">
            <span className="font-bold text-sm tracking-tight">Evaluación Oficial IA</span>
            <Badge variant="outline" className="border-primary/30 text-primary text-[10px] uppercase font-bold">
              AST Sandbox
            </Badge>
          </div>
        </div>

        {/* Center: Proctoring Telemetry status */}
        <div className="hidden md:flex items-center gap-2">
          <div className="flex items-center gap-1.5 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-medium text-primary">
            <span className="h-2 w-2 rounded-full bg-primary animate-pulse" />
            <ShieldCheck className="h-3.5 w-3.5" />
            <span>Monitoreo Activo: Cámara OK • Liveness OK • Foco Fijo</span>
          </div>
        </div>

        {/* Right: Timer & Finish */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 rounded-md bg-muted px-2.5 py-1 text-xs font-mono font-bold text-foreground">
            <Clock className="h-3.5 w-3.5 text-warning" />
            <span>44:59</span>
          </div>
          <Button size="sm" variant="destructive" className="h-8 text-xs font-semibold">
            Finalizar y Enviar
          </Button>
        </div>
      </header>

      {/* Main Workspace (Full-height without scrollbars on parent) */}
      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  )
}

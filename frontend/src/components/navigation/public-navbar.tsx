import { Link } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { ModeToggle } from "@/components/mode-toggle"
import { ArrowRight } from "lucide-react"

export function PublicNavbar() {
  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur-md supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-8">
        {/* Brand */}
        <Link to="/" className="flex items-center gap-2">
          <span className="font-extrabold text-xl tracking-tight text-primary">
            SkillMatch
          </span>
        </Link>

        {/* Center Nav */}
        <nav className="hidden md:flex items-center gap-7 text-xs font-semibold text-muted-foreground">
          <a href="#como-funciona" className="transition-colors hover:text-foreground">
            Cómo Funciona
          </a>
          <a href="#ia-demo" className="transition-colors hover:text-foreground">
            Validación IA
          </a>
          <a href="#catalogo" className="transition-colors hover:text-foreground">
            Catálogo
          </a>
          <a href="#confianza" className="transition-colors hover:text-foreground">
            Confianza & Escrow
          </a>
          <a href="#metricas" className="transition-colors hover:text-foreground">
            Estadísticas
          </a>
        </nav>

        {/* Right Actions */}
        <div className="flex items-center gap-3">
          <ModeToggle />
          <Button variant="ghost" size="sm" asChild className="text-xs font-semibold">
            <Link to="/app">Iniciar Sesión</Link>
          </Button>
          <Button size="sm" asChild className="bg-primary hover:bg-primary/90 text-primary-foreground text-xs font-semibold shadow-xs">
            <Link to="/app" className="flex items-center gap-1.5">
              <span>Empezar Gratis</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </Button>
        </div>
      </div>
    </header>
  )
}
